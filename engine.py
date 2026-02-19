import pulp
import time
from ortools.linear_solver import pywraplp


class OptimizationEngine:

    def __init__(self, df, solver_backend="PuLP",
                 time_limit=None, relative_gap=None):

        self.df = df
        self.backend = solver_backend

        self.time_limit = time_limit
        self.relative_gap = relative_gap

        self.var_type = None
        self.direction = None
        self.objective_col = None

        self.group_constraints = []
        self.linking_constraints = []

        self.budget_col = None
        self.budget_value = None

        self.model = None
        self.x_vars = {}

    def add_row_variable(self, var_type):

        self.var_type = var_type

        if self.backend == "PuLP":

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

    def set_objective(self, direction, column):

        self.direction = direction
        self.objective_col = column

        if self.backend == "PuLP":

            sense = pulp.LpMinimize if direction == "Minimize" else pulp.LpMaximize
            self.model = pulp.LpProblem("Optimization_Model", sense)

            self.model += pulp.lpSum(
                self.x_vars[i] * self.df.loc[i, column]
                for i in self.df.index
            )

    def add_group_constraint(self, group_col, sense, rhs_col):
        self.group_constraints.append((group_col, sense, rhs_col))

    def add_budget_constraint(self, amount_col, budget):

        self.budget_col = amount_col
        self.budget_value = budget

        if self.backend == "PuLP":
            self.model += pulp.lpSum(
                self.x_vars[i] * self.df.loc[i, amount_col]
                for i in self.df.index
            ) <= budget

    def add_linking_group(self, group_col, upper_col=None, lower_col=None):
        self.linking_constraints.append((group_col, upper_col, lower_col))

    def solve(self):

        if self.backend == "PuLP":
            return self._solve_pulp()
        else:
            return self._solve_ortools()

    # ==================================================
    # PuLP Solver (UNCHANGED)
    # ==================================================
    def _solve_pulp(self):

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

        for group_col, upper_col, lower_col in self.linking_constraints:

            y_group = {}
            for g in self.df[group_col].unique():
                y_group[g] = pulp.LpVariable(
                    f"y_{group_col}_{g}", cat="Binary"
                )

            for g in self.df[group_col].unique():
                idx = self.df[self.df[group_col] == g].index
                total = pulp.lpSum(self.x_vars[i] for i in idx)

                if upper_col:
                    upper = self.df.loc[idx[0], upper_col]
                    self.model += total <= upper * y_group[g]

                if lower_col:
                    lower = self.df.loc[idx[0], lower_col]
                    self.model += total >= lower * y_group[g]

        solver = pulp.PULP_CBC_CMD(
            timeLimit=self.time_limit,
            gapRel=self.relative_gap,
            msg=False
        )

        start = time.time()
        self.model.solve(solver)
        end = time.time()

        return {
            "status": pulp.LpStatus[self.model.status],
            "objective": pulp.value(self.model.objective),
            "solution": {
                i: pulp.value(self.x_vars[i]) for i in self.df.index
            },
            "solve_time": end - start,
            "gap": None
        }

    # ==================================================
    # OR-Tools Solver (STRICT PARITY + GAP FIX)
    # ==================================================
    def _solve_ortools(self):

        solver = pywraplp.Solver.CreateSolver("SCIP")
        if not solver:
            return {"status": "Solver unavailable"}

        if self.time_limit:
            solver.SetTimeLimit(int(self.time_limit * 1000))

        if self.relative_gap:
            solver.SetRelativeMipGap(self.relative_gap)

        x = {}

        for i in self.df.index:
            if self.var_type == "Continuous":
                x[i] = solver.NumVar(0, solver.infinity(), f"x_{i}")
            elif self.var_type == "Integer":
                x[i] = solver.IntVar(0, solver.infinity(), f"x_{i}")
            else:
                x[i] = solver.IntVar(0, 1, f"x_{i}")

        objective = solver.Objective()
        for i in self.df.index:
            objective.SetCoefficient(
                x[i],
                float(self.df.loc[i, self.objective_col])
            )

        if self.direction == "Minimize":
            objective.SetMinimization()
        else:
            objective.SetMaximization()

        for group_col, sense, rhs_col in self.group_constraints:
            for g in self.df[group_col].unique():
                idx = self.df[self.df[group_col] == g].index
                rhs = float(self.df.loc[idx[0], rhs_col])

                if sense == "==":
                    ct = solver.RowConstraint(rhs, rhs, "")
                elif sense == "<=":
                    ct = solver.RowConstraint(0, rhs, "")
                else:
                    ct = solver.RowConstraint(rhs, solver.infinity(), "")

                for i in idx:
                    ct.SetCoefficient(x[i], 1)

        if self.budget_value and self.budget_value > 0:
            ct = solver.RowConstraint(0, self.budget_value, "")
            for i in self.df.index:
                ct.SetCoefficient(
                    x[i],
                    float(self.df.loc[i, self.budget_col])
                )

        for group_col, upper_col, lower_col in self.linking_constraints:

            y = {}
            for g in self.df[group_col].unique():
                y[g] = solver.IntVar(0, 1, f"y_{group_col}_{g}")

            for g in self.df[group_col].unique():
                idx = self.df[self.df[group_col] == g].index

                if upper_col:
                    upper = float(self.df.loc[idx[0], upper_col])
                    ct = solver.RowConstraint(-solver.infinity(), 0, "")
                    for i in idx:
                        ct.SetCoefficient(x[i], 1)
                    ct.SetCoefficient(y[g], -upper)

                if lower_col:
                    lower = float(self.df.loc[idx[0], lower_col])
                    ct = solver.RowConstraint(0, solver.infinity(), "")
                    for i in idx:
                        ct.SetCoefficient(x[i], 1)
                    ct.SetCoefficient(y[g], -lower)

        start = time.time()
        status = solver.Solve()
        end = time.time()

        gap = None
        if solver.IsMip():
            try:
                best_bound = solver.Objective().BestBound()
                best_value = solver.Objective().Value()
                if best_value != 0:
                    gap = abs(best_bound - best_value) / abs(best_value)
            except:
                gap = None

        return {
            "status": "Optimal" if status == pywraplp.Solver.OPTIMAL else "Not Optimal",
            "objective": objective.Value(),
            "solution": {
                i: x[i].solution_value() for i in self.df.index
            },
            "solve_time": end - start,
            "gap": gap
        }
