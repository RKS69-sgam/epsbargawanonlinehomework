import streamlit as st
import pandas as pd
import gspread
import json
import base64
import plotly.express as px
from datetime import datetime, timedelta

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Principal Dashboard")
DATE_FORMAT = "%d-%m-%Y"

# === UTILITY FUNCTIONS ===
@st.cache_resource
def connect_to_gsheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
        credentials_dict = json.loads(decoded_creds)
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google APIs: {e}")
        return None

@st.cache_data(ttl=60)
def load_data(sheet_id):
    try:
        client = connect_to_gsheets()
        if client is None: return pd.DataFrame()
        sheet = client.open_by_key(sheet_id).sheet1
        all_values = sheet.get_all_values()
        if not all_values: return pd.DataFrame()
        df = pd.DataFrame(all_values[1:], columns=all_values[0])
        df.columns = df.columns.str.strip()
        df['Row ID'] = range(2, len(df) + 2)
        return df
    except Exception as e:
        st.error(f"Failed to load data for sheet ID {sheet_id}: {e}")
        return pd.DataFrame()

# === SHEET IDs ===
ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"
HOMEWORK_QUESTIONS_SHEET_ID = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
MASTER_ANSWER_SHEET_ID = "1lW2Eattf9kyhllV_NzMMq9tznibkhNJ4Ma-wLV5rpW0"
ANNOUNCEMENTS_SHEET_ID = "1zEAhoWC9_3UK09H4cFk6lRd6i5ChF3EknVc76L7zquQ"
ANSWER_BANK_SHEET_ID = "12S2YwNPHZIVtWSqXaRHIBakbFqoBVB4xcAcFfpwN3uw"

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "principal":
    st.error("You must be logged in as a Principal to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT & COPYRIGHT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)

# === PRINCIPAL DASHBOARD UI ===
st.header("🏛️ Principal Dashboard")

# --- Display Public Announcement (Updated) ---
try:
    announcements_df = load_data(ANNOUNCEMENTS_SHEET_ID)
    if not announcements_df.empty:
        today_str = datetime.today().strftime(DATE_FORMAT)
        
        # Filter for announcements with today's date
        todays_announcement = announcements_df[announcements_df.get('Date') == today_str]
        
        if not todays_announcement.empty:
            latest_message = todays_announcement['Message'].iloc[0]
            st.info(f"📢 **Public Announcement:** {latest_message}")
except Exception:
    # Fail silently if announcements can't be loaded
    pass
# ---------------------------------------------


# Load all necessary data once
df_users = load_data(ALL_USERS_SHEET_ID)
df_live_answers = load_data(MASTER_ANSWER_SHEET_ID)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET_ID)
df_answer_bank = load_data(ANSWER_BANK_SHEET_ID)

instruction_tab, report_tab, individual_tab = st.tabs(["Send Messages", "Performance Reports", "Individual Growth Charts"])

with instruction_tab:
    st.subheader("Send a Message")
    
    message_type = st.radio("Select message type:", ["Individual Instruction", "Public Announcement"])
    
    if message_type == "Individual Instruction":
        st.markdown("##### Send an Instruction to a Single User")
        if df_users.empty:
            st.warning("No users found in the database.")
        else:
            search_term = st.text_input("Search for a User by Name:")
            df_temp = df_users.copy()
            df_temp['display_name'] = df_temp.apply(
                lambda row: f"{row['User Name']} ({row['Class']})" if row['Role'] == 'Student' and row.get('Class') else row['User Name'],
                axis=1
            )
            if search_term:
                filtered_users = df_temp[df_temp['display_name'].str.contains(search_term, case=False, na=False)]
            else:
                filtered_users = df_temp
            
            user_list = ["---Select a User---"] + filtered_users['display_name'].tolist()

            with st.form("instruction_form"):
                selected_display_name = st.selectbox("Select a User", user_list)
                instruction_text = st.text_area("Instruction:")
                if st.form_submit_button("Send Instruction"):
                    if selected_display_name != "---Select a User---" and instruction_text:
                        real_user_name = selected_display_name.split(' (')[0]
                        user_row = df_users[df_users['User Name'] == real_user_name]
                        if not user_row.empty:
                            row_id = int(user_row.iloc[0]['Row ID'])
                            instruction_col = df_users.columns.get_loc('Instructions') + 1
                            client = connect_to_gsheets()
                            sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                            sheet.update_cell(row_id, instruction_col, instruction_text)
                            st.success(f"Instruction sent to {real_user_name}.")
                            load_data.clear()
                        else:
                            st.error("Selected user could not be found in the database.")
                    else:
                        st.warning("Please select a user and write an instruction.")

    elif message_type == "Public Announcement":
        with st.form("announcement_form"):
            announcement_text = st.text_area("Enter Public Announcement:")
            if st.form_submit_button("Broadcast Announcement"):
                if announcement_text:
                    client = connect_to_gsheets()
                    announcement_sheet_obj = client.open_by_key(ANNOUNCEMENTS_SHEET_ID).sheet1
                    
                    # Add today's date with the announcement
                    today_str = datetime.today().strftime(DATE_FORMAT)
                    announcement_sheet_obj.insert_row([announcement_text, today_str], 2)
                    
                    st.success("Public announcement sent to all dashboards!")
                    load_data.clear()
                else:
                    st.warning("Announcement text cannot be empty.")

with report_tab:
    st.subheader("Performance Reports")
    st.markdown("#### 📅 Today's Teacher Activity")
    
    today_str = datetime.today().strftime(DATE_FORMAT)
    df_teachers_report = df_users[df_users['Role'].isin(['Teacher', 'Admin', 'Principal'])].copy()
    todays_homework = df_homework[df_homework['Date'] == today_str]
    questions_created = todays_homework.groupby('Uploaded By').size().reset_index(name='Created Today')
    teacher_activity = pd.merge(df_teachers_report[['User Name']], questions_created, left_on='User Name', right_on='Uploaded By', how='left')
    teacher_activity.drop(columns=['Uploaded By'], inplace=True, errors='ignore')
    
    df_live_answers['Marks'] = pd.to_numeric(df_live_answers.get('Marks'), errors='coerce')
    ungraded_answers = df_live_answers[df_live_answers['Marks'].isna()]
    
    pending_summary_list = []
    for teacher_name in teacher_activity['User Name']:
        teacher_questions = df_homework[df_homework['Uploaded By'] == teacher_name]['Question'].tolist()
        pending_count = len(ungraded_answers[ungraded_answers['Question'].isin(teacher_questions)])
        pending_summary_list.append({'User Name': teacher_name, 'Pending Answers': pending_count})
        
    pending_df = pd.DataFrame(pending_summary_list)
    teacher_activity = pd.merge(teacher_activity, pending_df, on='User Name', how='left')
    teacher_activity.fillna(0, inplace=True)
    st.dataframe(teacher_activity)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🏆 Top Teachers Leaderboard (All Time)")
        df_teachers = df_users[df_users['Role'] == 'Teacher'].copy()
        df_teachers['Salary Points'] = pd.to_numeric(df_teachers.get('Salary Points', 0), errors='coerce').fillna(0)
        ranked_teachers = df_teachers.sort_values(by='Salary Points', ascending=False)
        ranked_teachers['Rank'] = range(1, len(ranked_teachers) + 1)
        st.dataframe(ranked_teachers[['User Name', 'Salary Points']])
        fig_teachers = px.bar(ranked_teachers, x='User Name', y='Salary Points', color='User Name', title='All Teachers by Performance Points')
        st.plotly_chart(fig_teachers, use_container_width=True)

    with col2:
        st.markdown("#### 📉 Students Needing Improvement")
        df_students = df_users[df_users['Role'] == 'Student']
        if not df_answer_bank.empty:
            df_answer_bank['Marks'] = pd.to_numeric(df_answer_bank.get('Marks'), errors='coerce')
            graded_answers = df_answer_bank.dropna(subset=['Marks'])
            if not graded_answers.empty:
                student_performance = graded_answers.groupby('Student Gmail')['Marks'].mean().reset_index()
                merged_df = pd.merge(student_performance, df_students, left_on='Student Gmail', right_on='Gmail ID')
                weakest_students = merged_df.nsmallest(5, 'Marks').round(2)
                st.dataframe(weakest_students[['User Name', 'Class', 'Marks']])
            else:
                st.info("No graded answers in Answer Bank.")
        else:
            st.info("Answer Bank is empty.")

    st.markdown("---")
    
    # Top 3 Students (from Answer Bank)
    st.subheader("🥇 Class-wise Top 3 Students")
    df_students_report = df_users[df_users['Role'] == 'Student']
    if df_answer_bank.empty or df_students_report.empty:
        st.info("Leaderboard will be generated once answers are graded and moved to the bank.")
    else:
        df_answer_bank['Marks'] = pd.to_numeric(df_answer_bank.get('Marks'), errors='coerce')
        graded_answers = df_answer_bank.dropna(subset=['Marks'])
        if graded_answers.empty:
            st.info("The leaderboard is available after answers have been graded and moved to the bank.")
        else:
            df_merged = pd.merge(graded_answers, df_students_report, left_on='Student Gmail', right_on='Gmail ID', suffixes=('_ans', '_user'))
            leaderboard_df = df_merged.groupby(['Class_user', 'User Name'])['Marks'].mean().reset_index()
            leaderboard_df.rename(columns={'Class_user': 'Class'}, inplace=True)
            leaderboard_df['Rank'] = leaderboard_df.groupby('Class')['Marks'].rank(method='dense', ascending=False).astype(int)
            leaderboard_df = leaderboard_df.sort_values(by=['Class', 'Rank'])
            top_students_df = leaderboard_df.groupby('Class').head(3).reset_index(drop=True)
            top_students_df['Marks'] = top_students_df['Marks'].round(2)
            
            st.markdown("#### Top Performers Summary")
            st.dataframe(top_students_df[['Rank', 'User Name', 'Class', 'Marks']])

            # --- NEW: Graph for Top Students ---
            fig_students = px.bar(
                top_students_df,
                x='User Name',
                y='Marks',
                color='Class',
                title='Top 3 Students by Average Marks per Class',
                labels={'Marks': 'Average Marks', 'User Name': 'Student'},
                text='Marks'
            )
            fig_students.update_traces(textposition='outside')
            st.plotly_chart(fig_students, use_container_width=True)
            # ------------------------------------
    st.markdown("---")

with individual_tab:
    st.subheader("Individual Growth Charts")
    report_type = st.selectbox("Select report type", ["Student", "Teacher"])

    if report_type == "Student":
        df_students = df_users[df_users['Role'] == 'Student'].copy()
        
        # --- FIX: Create display name with class ---
        df_students['display_name'] = df_students.apply(
            lambda row: f"{row['User Name']} ({row['Class']})" if row.get('Class') else row['User Name'],
            axis=1
        )
        student_list = df_students['display_name'].tolist()
        
        search_student = st.text_input("Search Student Name:")
        if search_student:
            student_list = [name for name in student_list if search_student.lower() in name.lower()]

        if not student_list:
            st.warning("No students found.")
        else:
            selected_display_name = st.selectbox("Select Student", ["---Select---"] + student_list)
            
            if selected_display_name != "---Select---":
                # --- FIX: Extract real name to find the user ---
                real_name = selected_display_name.split(' (')[0]
                student_gmail = df_students[df_students['User Name'] == real_name].iloc[0]['Gmail ID']
                
                student_answers = df_answer_bank[df_answer_bank['Student Gmail'] == student_gmail].copy()
                if not student_answers.empty:
                    student_answers['Marks'] = pd.to_numeric(student_answers['Marks'], errors='coerce')
                    graded_answers = student_answers.dropna(subset=['Marks'])
                    if not graded_answers.empty:
                        fig = px.bar(graded_answers, x='Subject', y='Marks', color='Subject', title=f"Subject-wise Performance for {selected_display_name}")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info(f"{selected_display_name} has no graded answers yet.")
                else:
                    st.info(f"{selected_display_name} has not submitted any answers to the Answer Bank yet.")

    elif report_type == "Teacher":
        df_teachers = df_users[df_users['Role'] == 'Teacher']
        teacher_list = df_teachers['User Name'].tolist()
        
        search_teacher = st.text_input("Search Teacher Name:")
        if search_teacher:
            teacher_list = [name for name in teacher_list if search_teacher.lower() in name.lower()]
            
        if not teacher_list:
            st.warning("No teachers found.")
        else:
            teacher_name = st.selectbox("Select Teacher", ["---Select---"] + teacher_list)
            if teacher_name != "---Select---":
                teacher_homework = df_homework[df_homework['Uploaded By'] == teacher_name]
                if not teacher_homework.empty:
                    questions_by_subject = teacher_homework.groupby('Subject').size().reset_index(name='Question Count')
                    fig = px.bar(questions_by_subject, x='Subject', y='Question Count', color='Subject', title=f"Homework Created by {teacher_name}")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"{teacher_name} has not created any homework yet.")


st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>© 2025 PRK Home Tuition. All Rights Reserved.</p>", unsafe_allow_html=True)
