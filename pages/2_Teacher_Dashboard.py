import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")
DATE_FORMAT = "%d-%m-%Y"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}
GRADE_MAP_REVERSE = {v: k for k, v in GRADE_MAP.items()}

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
ANSWER_BANK_SHEET_ID = "12S2YwNPHZIVtWSqXaRHIBakbFqoBVB4xcAcFfpwN3uw"
ANNOUNCEMENTS_SHEET_ID = "1zEAhoWC9_3UK09H4cFk6lRd6i5ChF3EknVc76L7zquQ"

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher to access this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT & COPYRIGHT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)

# === TEACHER DASHBOARD UI ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

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

    
# --- INSTRUCTION, ANNOUNCEMENT & SALARY NOTIFICATION ---
df_users = load_data(ALL_USERS_SHEET_ID)
teacher_info_row = df_users[df_users['Gmail ID'] == st.session_state.user_gmail]
if not teacher_info_row.empty:
    teacher_info = teacher_info_row.iloc[0]
    points_str = str(teacher_info.get('Salary Points', '0')).strip()
    salary_points = int(points_str) if points_str.isdigit() else 0

    if salary_points >= 5000:
        st.success("🎉 Congratulations! You have earned 5000+ points. Please contact administration to register your salary account.")
        st.balloons()
    
    instruction = teacher_info.get('Instruction', '').strip()
    reply = teacher_info.get('Instruction_Reply', '').strip()
    status = teacher_info.get('Instruction_Status', '')
    if status == 'Sent' and instruction and not reply:
        st.warning(f"**New Instruction from Principal:** {instruction}")
        with st.form(key="reply_form"):
            reply_text = st.text_area("Your Reply:")
            if st.form_submit_button("Send Reply"):
                if reply_text:
                    row_id = int(teacher_info.get('Row ID'))
                    reply_col = df_users.columns.get_loc('Instruction_Reply') + 1
                    status_col = df_users.columns.get_loc('Instruction_Status') + 1
                    sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                    sheet.update_cell(row_id, reply_col, reply_text)
                    sheet.update_cell(row_id, status_col, "Replied")
                    st.success("Your reply has been sent.")
                    load_data.clear()
                    st.rerun()
                else:
                    st.warning("Reply cannot be empty.")
    st.markdown("---")

# Load other necessary data
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET_ID)
df_live_answers = load_data(MASTER_ANSWER_SHEET_ID)
df_answer_bank = load_data(ANSWER_BANK_SHEET_ID)

# Display a summary of today's submitted homework
st.subheader("Today's Submitted Homework")
today_str = datetime.today().strftime(DATE_FORMAT)
todays_homework = df_homework[(df_homework.get('Uploaded By') == st.session_state.user_name) & (df_homework.get('Date') == today_str)]

if todays_homework.empty:
    st.info("You have not created any homework assignments today.")
else:
    if 'selected_assignment' not in st.session_state:
        summary_table = pd.pivot_table(todays_homework, index='Class', columns='Subject', aggfunc='size', fill_value=0)
        st.markdown("#### Summary Table")
        st.dataframe(summary_table)
        st.markdown("---")
        st.markdown("#### View Details")
        for class_name, row in summary_table.iterrows():
            for subject_name, count in row.items():
                if count > 0:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"**Class:** {class_name} | **Subject:** {subject_name}")
                    with col2:
                        if st.button(f"View {count} Questions", key=f"view_{class_name}_{subject_name}"):
                            st.session_state.selected_assignment = {'Class': class_name, 'Subject': subject_name, 'Date': today_str}
                            st.rerun()
    
    if 'selected_assignment' in st.session_state:
        st.markdown("---")
        st.subheader("Viewing Questions for Selected Assignment")
        selected = st.session_state.selected_assignment
        st.info(f"Class: **{selected['Class']}** | Subject: **{selected['Subject']}** | Date: **{selected['Date']}**")
        selected_questions = df_homework[
            (df_homework['Class'] == selected['Class']) &
            (df_homework['Subject'] == selected['Subject']) &
            (df_homework['Date'] == selected['Date'])
        ]
        for i, row in enumerate(selected_questions.itertuples()):
            st.write(f"{i + 1}. {row.Question}")
        if st.button("Back to Main View"):
            del st.session_state.selected_assignment
            st.rerun()

st.markdown("---")

# --- NEW TAB SYSTEM USING st.radio ---
selected_tab = st.radio(
    "Navigation",
    ["Create Homework", "Grade Answers", "My Reports"],
    horizontal=True,
    label_visibility="collapsed"
)

if selected_tab == "Create Homework":
    st.subheader("Create a New Homework Assignment")
    if 'context_set' not in st.session_state:
        st.session_state.context_set = False
    if not st.session_state.context_set:
        with st.form("context_form"):
            subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"])
            cls = st.selectbox("Class", [f"{i}th" for i in range(5, 13)])
            date = st.date_input("Date", datetime.today(), format="DD-MM-YYYY")
            if st.form_submit_button("Start Adding Questions →"):
                st.session_state.context_set = True
                st.session_state.homework_context = {"subject": subject, "class": cls, "date": date}
                st.session_state.questions_list = []
                st.rerun()
    if st.session_state.context_set:
        ctx = st.session_state.homework_context
        st.success(f"Creating homework for: **{ctx['class']} - {ctx['subject']}** (Date: {ctx['date'].strftime(DATE_FORMAT)})")
        with st.form("add_question_form", clear_on_submit=True):
            question_text = st.text_area("Enter a question to add:", height=100)
            if st.form_submit_button("Add Question") and question_text:
                st.session_state.questions_list.append(question_text)
        if st.session_state.questions_list:
            st.write("#### Current Questions:")
            for i, q in enumerate(st.session_state.questions_list):
                st.write(f"{i + 1}. {q}")
            if st.button("Final Submit Homework"):
                client = connect_to_gsheets()
                sheet = client.open_by_key(HOMEWORK_QUESTIONS_SHEET_ID).sheet1
                rows_to_add = [[ctx['class'], ctx['date'].strftime(DATE_FORMAT), st.session_state.user_name, ctx['subject'], q] for q in st.session_state.questions_list]
                sheet.append_rows(rows_to_add, value_input_option='USER_ENTERED')
                load_data.clear()
                st.success("Homework submitted successfully!")
                del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
                st.rerun()
        if st.session_state.context_set and st.button("Create Another Homework (Reset)"):
            del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
            st.rerun()
    st.markdown("---")

elif selected_tab == "Grade Answers":
    st.subheader("Grade Student Answers")
    
    my_questions = df_homework[df_homework.get('Uploaded By') == st.session_state.user_name]['Question'].tolist()
    answers_to_my_questions = df_live_answers[df_live_answers['Question'].isin(my_questions)].copy()
    answers_to_my_questions['Marks'] = pd.to_numeric(answers_to_my_questions.get('Marks'), errors='coerce')
    ungraded = answers_to_my_questions[answers_to_my_questions['Marks'].isna()]

    if ungraded.empty:
        st.success("🎉 All answers for your questions have been graded!")
    else:
        student_gmails = ungraded['Student Gmail'].unique().tolist()
        df_students = df_users[df_users['Role'] == 'Student']
        gradable_students = df_students[df_students['Gmail ID'].isin(student_gmails)].copy()

        if gradable_students.empty:
            st.info("No confirmed students have pending answers for your questions.")
        else:
            gradable_students['display_name'] = gradable_students.apply(
                lambda row: f"{row['User Name']} ({row['Class']})" if row.get('Class') else row['User Name'],
                axis=1
            )
            student_list = ["---Select Student---"] + gradable_students['display_name'].tolist()
            
            selected_student_display = st.selectbox("Select Student", student_list)

            if selected_student_display != "---Select Student---":
                real_user_name = selected_student_display.split(' (')[0]
                selected_gmail = gradable_students[gradable_students['User Name'] == real_user_name].iloc[0]['Gmail ID']
                
                student_answers_df = ungraded[ungraded['Student Gmail'] == selected_gmail]
                st.markdown(f"#### Grading answers for: **{real_user_name}**")
                
                for index, row in student_answers_df.sort_values(by='Date', ascending=False).iterrows():
                    st.write(f"**Question:** {row.get('Question')}")
                    st.info(f"**Answer:** {row.get('Answer')}")
                    
                    with st.form(key=f"grade_form_{index}"):
                        grade_options = ["---Select Grade---"] + list(GRADE_MAP.keys())
                        grade = st.selectbox("Grade", grade_options, key=f"grade_{index}")
                        remarks = ""
                        
                        if grade in ["Needs Improvement", "Average", "Good"]:
                            remarks = st.text_area("Remarks/Feedback (Required)", key=f"remarks_{index}")
                        
                        if st.form_submit_button("Save Grade"):
                            if grade == "---Select Grade---":
                                st.warning("Please select a valid grade.")
                            elif grade in ["Needs Improvement", "Average", "Good"] and not remarks.strip():
                                st.warning("Remarks are required for this grade.")
                            else:
                                with st.spinner("Saving..."):
                                    client = connect_to_gsheets()
                                    row_id_to_update = int(row.get('Row ID'))
                                    
                                    if grade in ["Very Good", "Outstanding"]:
                                        live_sheet = client.open_by_key(MASTER_ANSWER_SHEET_ID).sheet1
                                        answer_bank_sheet = client.open_by_key(ANSWER_BANK_SHEET_ID).sheet1
                                        
                                        row_to_move = df_live_answers.loc[index].copy()
                                        row_to_move['Marks'] = GRADE_MAP[grade]
                                        row_to_move['Remarks'] = remarks
                                        
                                        row_values_to_append = row_to_move.drop('Row ID').tolist()
                                        
                                        answer_bank_sheet.append_row(row_values_to_append, value_input_option='USER_ENTERED')
                                        live_sheet.delete_rows(row_id_to_update)
                                        st.success("Grade saved and moved to Answer Bank!")
                                        # --- FIX: Safely handle Salary Points increment ---
                                        teacher_info_row = df_users[df_users['Gmail ID'] == st.session_state.user_gmail]
                                        if not teacher_info_row.empty:
                                            teacher_row_id = int(teacher_info_row.iloc[0].get('Row ID'))
                
                                            # Safely get the current points, defaulting to 0 if empty or not a number
                                            points_str = str(teacher_info_row.iloc[0].get('Salary Points', '0')).strip()
                                            current_points = int(points_str) if points_str.isdigit() else 0
                
                                            new_points = current_points + 1
                                            points_col = list(df_users.columns).index("Salary Points") + 1
                                            user_sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                                            user_sheet.update_cell(teacher_row_id, points_col, new_points)
            
                                            load_data.clear()
                                            st.success("Saved!")
                                            st.rerun()
                                    else:
                                        live_sheet = client.open_by_key(MASTER_ANSWER_SHEET_ID).sheet1
                                        marks_col = list(df_live_answers.columns).index("Marks") + 1
                                        remarks_col = list(df_live_answers.columns).index("Remarks") + 1
                                        live_sheet.update_cell(row_id_to_update, marks_col, GRADE_MAP[grade])
                                        live_sheet.update_cell(row_id_to_update, remarks_col, remarks)
                                        st.success("Grade and remarks saved!")
                                    
                                    teacher_info_row = df_users[df_users['Gmail ID'] == st.session_state.user_gmail]
                                    if not teacher_info_row.empty:
                                        teacher_row_id = int(teacher_info_row.iloc[0].get('Row ID'))
                                        current_points = int(teacher_info_row.iloc[0].get('Salary Points', 0))
                                        new_points = current_points + 1
                                        points_col = list(df_users.columns).index("Salary Points") + 1
                                        user_sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                                        user_sheet.update_cell(teacher_row_id, points_col, new_points)
                                    
                                    load_data.clear()
                                    st.rerun()
                    st.markdown("---")

elif selected_tab == "My Reports":
    st.subheader("My Reports")
    
    # Report 1: Homework Creation Report
    st.markdown("#### Homework Creation Report")
    teacher_homework = df_homework[df_homework.get('Uploaded By') == st.session_state.user_name]
    if teacher_homework.empty:
        st.info("No homework created yet.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.today() - timedelta(days=7), format="DD-MM-YYYY")
        with col2:
            end_date = st.date_input("End Date", datetime.today(), format="DD-MM-YYYY")
        
        teacher_homework['Date_dt'] = pd.to_datetime(teacher_homework['Date'], format=DATE_FORMAT, errors='coerce').dt.date
        filtered_report = teacher_homework[
            (teacher_homework['Date_dt'] >= start_date) &
            (teacher_homework['Date_dt'] <= end_date)
        ]
        if filtered_report.empty:
            st.warning("No homework found in the selected date range.")
        else:
            summary = filtered_report.groupby(['Class', 'Subject']).size().reset_index(name='Total Questions')
            st.dataframe(summary)
            fig = px.bar(summary, x='Class', y='Total Questions', color='Subject', title='Your Homework Contributions')
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    
    # Report 2: Top Teachers Leaderboard
    st.subheader("🏆 Top Teachers Leaderboard")
    df_all_teachers = df_users[df_users['Role'] == 'Teacher'].copy()
    if 'Salary Points' in df_all_teachers.columns:
        df_all_teachers['Salary Points'] = pd.to_numeric(df_all_teachers.get('Salary Points', 0), errors='coerce').fillna(0)
        ranked_teachers = df_all_teachers.sort_values(by='Salary Points', ascending=False)
        ranked_teachers['Rank'] = range(1, len(ranked_teachers) + 1)
        
        st.dataframe(ranked_teachers[['Rank', 'User Name', 'Salary Points']])

        # --- NEW: Graph for Top Teachers ---
        fig_teachers = px.bar(
            ranked_teachers.head(10), 
            x='User Name', 
            y='Salary Points', 
            color='User Name',
            title='Top Teachers by Performance Points',
            labels={'Salary Points': 'Total Points', 'User Name': 'Teacher'},
            text='Salary Points'
        )
        fig_teachers.update_traces(textposition='outside')
        st.plotly_chart(fig_teachers, use_container_width=True)
        # ------------------------------------
    else:
        st.warning("'Salary Points' column not found in All Users Sheet.")

    st.markdown("---")

    # Report 3: Top 3 Students (from Answer Bank)
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
st.markdown("<p style='text-align: center; color: grey;'>© 2025 PRK Home Tuition. All Rights Reserved.</p>", unsafe_allow_html=True)
