import pandas as pd
import numpy as np
import re

def load_and_process_data(file_path):
    """
    Universal Data Loader.
    1. Detects Class Name from top rows (e.g., '5TH D').
    2. Auto-detects Header Row (Name/Activity columns).
    3. Handles 'Merged Cells' (Forward Fill) for grouped student data.
    4. Handles 'AB' (Absent) or text in score columns gracefully.
    """
    print(f"Loading file: {file_path}")
    
    try:
        # Read raw data with no header to scan manually
        if file_path.endswith('.csv'):
            df_raw = pd.read_csv(file_path, header=None)
        else:
            df_raw = pd.read_excel(file_path, header=None)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not read file. {e}")
        return [], {}, None

    # --- STEP 1: DETECT CLASS NAME INSIDE FILE ---
    detected_class = None
    # Scan the first 5 rows and 5 columns for a class string
    for r in range(min(5, len(df_raw))):
        for c in range(min(5, len(df_raw.columns))):
            val = str(df_raw.iloc[r, c]).strip()
            # Look for patterns like "5TH D", "Class 5", "5 D"
            # We skip "Student Name" or generic headers
            if len(val) < 10 and any(char.isdigit() for char in val) and "week" not in val.lower():
                detected_class = val
                break
        if detected_class: break
    
    if detected_class:
        print(f"Internal Class Detection: Found '{detected_class}' inside Excel.")

    # --- STEP 2: FIND HEADER ROW & COLUMNS ---
    header_row_idx = -1
    name_col_idx = -1
    activity_col_idx = -1

    # Keywords to identify columns
    name_keywords = ['student name', 'name', 'roll number', 'student']
    activity_keywords = ['co-curriculars', 'activity', 'area', 'skill', 'subject']

    for r_idx, row in df_raw.head(15).iterrows():
        row_str = " ".join([str(v).lower() for v in row.values])
        
        # Check if row contains both Name and Activity keywords
        has_name = any(k in row_str for k in name_keywords)
        has_activity = any(k in row_str for k in activity_keywords)
        
        if has_name and has_activity:
            header_row_idx = r_idx
            # Now pinpoint the exact column indices
            for c_idx, val in enumerate(row.values):
                val_str = str(val).lower()
                if any(k in val_str for k in name_keywords) and name_col_idx == -1:
                    name_col_idx = c_idx
                if any(k in val_str for k in activity_keywords):
                    activity_col_idx = c_idx
            break
    
    # Defaults if recognition fails
    if header_row_idx == -1:
        print("Warning: Header detection failed. Using default structure.")
        header_row_idx = 1 # Based on your screenshot, header is often row 1 or 2
        name_col_idx = 0
        activity_col_idx = 1
    
    print(f"Mapping: Header Row={header_row_idx}, Name Col={name_col_idx}, Activity Col={activity_col_idx}")

    # --- STEP 3: PROCESS DATA (With Forward Fill) ---
    students = []
    all_scores = {}
    
    # We use this to remember the current student across empty rows
    current_student_entry = None 
    
    total_cols = df_raw.shape[1]
    
    for index, row in df_raw.iloc[header_row_idx+1:].iterrows():
        # Get raw values
        raw_name_cell = row.iloc[name_col_idx] if name_col_idx < total_cols else None
        activity_cell = row.iloc[activity_col_idx] if activity_col_idx < total_cols else None
        
        # 1. NAME LOGIC
        name_text = ""
        if pd.notna(raw_name_cell):
            name_text = str(raw_name_cell).strip()
            
        # Ignore junk rows (repeated headers)
        if name_text.lower() in ['student name', 'roll number', 'name / roll number']:
            continue

        # IF we have a name, it's a NEW student
        if name_text:
            # Create new student object
            current_student_entry = {
                'name': name_text,
                'activities': {}
            }
            students.append(current_student_entry)
        
        # IF name is empty, we stay with 'current_student_entry' (The Forward Fill)
        # We only process if we have an active student and a valid activity
        if current_student_entry and pd.notna(activity_cell):
            activity_name = str(activity_cell).strip()
            if not activity_name: continue

            scores = []
            feedbacks = []
            
            # Start scanning for data (Score, Feedback, Score, Feedback...)
            # Based on screenshot: Activity is Col B. Data starts Col C.
            start_col = activity_col_idx + 1
            
            for i in range(start_col, total_cols, 2):
                score_val = row.iloc[i]
                feedback_val = row.iloc[i+1] if (i+1) < total_cols else None
                
                # Check Score Validity
                if pd.notna(score_val):
                    s_str = str(score_val).strip().upper()
                    
                    # Handle "AB" or text -> Skip adding to average, but maybe keep feedback
                    if s_str.replace('.','',1).isdigit():
                        s = float(s_str)
                        if 0 <= s <= 100:
                            scores.append(s)
                            # Add to global stats
                            if activity_name not in all_scores: all_scores[activity_name] = []
                            all_scores[activity_name].append(s)
                    
                    # Capture feedback regardless of score (even if 'AB')
                    if pd.notna(feedback_val):
                        feedbacks.append(str(feedback_val).strip())

            # Calculate Average (only if we have valid numeric scores)
            # If no scores (e.g. all 'AB'), average is 0
            student_avg = np.mean(scores) if scores else 0
            
            # Save to student object
            current_student_entry['activities'][activity_name] = {
                'scores': scores,
                'feedbacks': feedbacks,
                'average': student_avg
            }

    class_averages = {k: np.mean(v) for k, v in all_scores.items()}
    
    return students, class_averages, detected_class