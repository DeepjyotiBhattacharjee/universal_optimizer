import pulp


class OptimizationEngine:

    def __init__(self, df):
        self.df = df
        self.model = None
        self.x_vars = {}
        self.y_vars = {}
        self.objective = None
        self.group_constraints = []
        self.linking_constraints = []

    # ----------------------------
    # Add row decision variable
    # ----------------------------
    def add_row_variable(self, var_type):

        cat_map = {
            "Continuous": pulp.LpContinuous,
            "Integer": pulp.LpInteger,
            "Binary": pulp.LpBinary
        }

        self.x_vars = {
            i: pulp.LpVariable(
                f"x_{i}",
                lowBound=0,
                cat=cat_map[var_type]
            )
            for i in self.df.index
        }

    # ----------------------------
    # Objective
    # ----------------------------
    def set_objective(self, direction, column):

        sense = pulp.LpMinimize if direction == "Minimize" else pulp.LpMaximize
        self.model = pulp.LpProblem("Optimization_Model", sense)

        self.model += pulp.lpSum(
            self.x_vars[i] * self.df.loc[i, column]
            for i in self.df.index
        )

    # ----------------------------
    # Add normal group constraint
    # ----------------------------
    def add_group_constraint(self, group_col, sense, rhs_col):
        self.group_constraints.append((group_col, sense, rhs_col))

    # ----------------------------
    # Add budget constraint
    # ----------------------------
    def add_budget_constraint(self, amount_col, budget):

        self.model += pulp.lpSum(
            self.x_vars[i] * self.df.loc[i, amount_col]
            for i in self.df.index
        ) <= budget


    # ----------------------------
    # Add linking constraint definition
    # ----------------------------
    def add_linking_group(self, group_col, upper_col=None, lower_col=None):
        self.linking_constraints.append((group_col, upper_col, lower_col))

    # ----------------------------
    # Solve
    # ----------------------------
    def solve(self):

        # Apply normal group constraints
        for group_col, sense, rhs_col in self.group_constraints:

            for g in self.df[group_col].unique():

                idx = self.df[self.df[group_col] == g].index
                lhs = pulp.lpSum(self.x_vars[i] for i in idx)
                rhs = self.df.loc[idx[0], rhs_col]

                if sense == "<=":
                    self.model += lhs <= rhs
                elif sense == ">=":
                    self.model += lhs >= rhs
                else:
                    self.model += lhs == rhs

        # Apply linking constraints
        for group_col, upper_col, lower_col in self.linking_constraints:

            # Create binary variables per group
            y_group = {}

            for g in self.df[group_col].unique():
                y_group[g] = pulp.LpVariable(f"y_{group_col}_{g}", cat="Binary")

            for g in self.df[group_col].unique():

                idx = self.df[self.df[group_col] == g].index
                total = pulp.lpSum(self.x_vars[i] for i in idx)

                if upper_col:
                    upper = self.df.loc[idx[0], upper_col]
                    self.model += total <= upper * y_group[g]

                if lower_col:
                    lower = self.df.loc[idx[0], lower_col]
                    self.model += total >= lower * y_group[g]

        self.model.solve()

        return {
            "status": pulp.LpStatus[self.model.status],
            "objective": pulp.value(self.model.objective),
            "solution": {
                            i: pulp.value(self.x_vars[i]) for i in self.df.index
            }
        }
