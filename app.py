import streamlit as st
import pandas as pd
from engine import OptimizationEngine

st.set_page_config(layout="wide")
st.title("🧠 Universal Optimization Builder")

# Sidebar Solver Selection
st.sidebar.title("Solver Settings")
solver_choice = st.sidebar.selectbox(
    "Choose Solver Backend",
    ["PuLP", "OR-Tools", "Compare Both"]
)

# Upload dataset
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

        if solver_choice != "Compare Both":

            engine = OptimizationEngine(df, solver_backend=solver_choice)

            engine.add_row_variable(var_type)
            engine.set_objective(direction, objective_col)

            if budget_value > 0:
                engine.add_budget_constraint(budget_col, budget_value)

            for gc in st.session_state.group_constraints:
                engine.add_group_constraint(*gc)

            for lg in st.session_state.linking_groups:
                engine.add_linking_group(*lg)

            result = engine.solve()

            st.write("Status:", result["status"])
            st.write("Objective Value:", result["objective"])
            st.write("Solve Time (seconds):", round(result["solve_time"], 6))

            df["Decision"] = df.index.map(result["solution"])
            selected_df = df[df["Decision"] > 0]

            st.subheader("Selected Records")
            st.dataframe(selected_df)

        else:

            results = []

            for backend in ["PuLP", "OR-Tools"]:

                engine = OptimizationEngine(df, solver_backend=backend)

                engine.add_row_variable(var_type)
                engine.set_objective(direction, objective_col)

                if budget_value > 0:
                    engine.add_budget_constraint(budget_col, budget_value)

                for gc in st.session_state.group_constraints:
                    engine.add_group_constraint(*gc)

                for lg in st.session_state.linking_groups:
                    engine.add_linking_group(*lg)

                result = engine.solve()

                results.append({
                    "Solver": backend,
                    "Status": result["status"],
                    "Objective": result["objective"],
                    "Solve Time (sec)": round(result["solve_time"], 6)
                })

            st.subheader("Solver Comparison")
            st.dataframe(pd.DataFrame(results))
