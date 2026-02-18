import streamlit as st
import pandas as pd
from engine import OptimizationEngine

st.set_page_config(layout="wide")
st.title("🧠 Universal Optimization Builder")

st.sidebar.title("Solver Settings")
solver_choice = st.sidebar.selectbox(
    "Choose Solver Backend",
    ["PuLP", "OR-Tools", "Compare Both"]
)

time_limit = st.sidebar.number_input("Time Limit (seconds, 0 = no limit)", min_value=0.0)
relative_gap = st.sidebar.number_input("Relative Gap (e.g. 0.02 for 2%)", min_value=0.0)

st.header("1️⃣ Upload Dataset")
file = st.file_uploader("Upload CSV")

if file:

    df = pd.read_csv(file)
    st.dataframe(df.head())

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    all_cols = df.columns.tolist()

    st.header("2️⃣ Decision Variable")
    var_type = st.radio("Decision Type", ["Continuous", "Integer", "Binary"])

    st.header("3️⃣ Objective")
    direction = st.radio("Goal", ["Minimize", "Maximize"])
    objective_col = st.selectbox("Objective Column", numeric_cols)

    st.header("4️⃣ Group Constraints")

    if "group_constraints" not in st.session_state:
        st.session_state.group_constraints = []

    group_col = st.selectbox("Group Column", all_cols)
    sense = st.selectbox("Relation", ["<=", ">=", "=="])
    rhs_col = st.selectbox("Right-Hand Column", numeric_cols)

    if st.button("Add Group Constraint"):
        st.session_state.group_constraints.append((group_col, sense, rhs_col))

    st.write("Added Group Constraints:")
    for gc in st.session_state.group_constraints:
        st.write(gc)

    st.header("5️⃣ Linking Constraints")

    if "linking_groups" not in st.session_state:
        st.session_state.linking_groups = []

    link_group_col = st.selectbox("Linking Group Column", all_cols)
    upper_col = st.selectbox("Upper Bound Column (Optional)", ["None"] + numeric_cols)
    lower_col = st.selectbox("Lower Bound Column (Optional)", ["None"] + numeric_cols)

    if st.button("Add Linking Group"):
        st.session_state.linking_groups.append(
            (
                link_group_col,
                None if upper_col == "None" else upper_col,
                None if lower_col == "None" else lower_col
            )
        )

    st.write("Added Linking Groups:")
    for lg in st.session_state.linking_groups:
        st.write(lg)

    st.header("Budget Constraint (Optional)")
    budget_col = st.selectbox("Amount Column for Budget", numeric_cols)
    budget_value = st.number_input("Enter Budget (0 = ignore)", min_value=0.0)

    st.header("6️⃣ Solve")

    if st.button("Run Optimization"):

        def run_solver(backend, tl=None, gap=None):

            engine = OptimizationEngine(
                df,
                solver_backend=backend,
                time_limit=tl if tl > 0 else None,
                relative_gap=gap if gap > 0 else None
            )

            engine.add_row_variable(var_type)
            engine.set_objective(direction, objective_col)

            if budget_value > 0:
                engine.add_budget_constraint(budget_col, budget_value)

            for gc in st.session_state.group_constraints:
                engine.add_group_constraint(*gc)

            for lg in st.session_state.linking_groups:
                engine.add_linking_group(*lg)

            return engine.solve()

        if solver_choice != "Compare Both":

            result = run_solver(
                solver_choice,
                time_limit,
                relative_gap
            )

            st.write("Status:", result["status"])
            st.write("Objective Value:", result["objective"])
            st.write("Solve Time:", round(result["solve_time"], 6))
            st.write("Gap:", result["gap"])

            df["Decision"] = df.index.map(result["solution"])
            st.subheader("Selected Records")
            st.dataframe(df[df["Decision"] > 0])

        else:

            full = run_solver(solver_choice="PuLP" if solver_choice == "Compare Both" else solver_choice)

            early = run_solver(
                backend="PuLP",
                tl=time_limit,
                gap=relative_gap
            )

            comparison = pd.DataFrame([
                {
                    "Mode": "Full Optimal",
                    "Objective": full["objective"],
                    "Time": round(full["solve_time"], 6),
                    "Gap": full["gap"],
                    "Status": full["status"]
                },
                {
                    "Mode": "Early Stop",
                    "Objective": early["objective"],
                    "Time": round(early["solve_time"], 6),
                    "Gap": early["gap"],
                    "Status": early["status"]
                }
            ])

            st.subheader("Comparison")
            st.dataframe(comparison)

            st.subheader("Full Solution Records")
            df["Decision"] = df.index.map(full["solution"])
            st.dataframe(df[df["Decision"] > 0])

            st.subheader("Early Stop Solution Records")
            df["Decision"] = df.index.map(early["solution"])
            st.dataframe(df[df["Decision"] > 0])
