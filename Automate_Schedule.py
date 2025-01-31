#!/usr/bin/env python
# coding: utf-8

# In[37]:


import gradio as gr
import pandas as pd
from datetime import datetime, timedelta
import itertools
import random
import json
import os

# File to store persistent data
DATA_FILE = "schedule_data.json"

# Function to save all data to a JSON file
def save_all_data(data):
    work_group = data["work_group"]
    unavailabilities = data["unavailabilities"]
    schedules = data["schedules"]

    new_data = {
        "work_group": work_group,
        "unavailabilities": {
            person: [(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")) for start, end in unavails]
            for person, unavails in unavailabilities.items()
        },
        "schedules": [
            {
                "start_date": schedule["start_date"].strftime("%Y-%m-%d"),
                "end_date": schedule["end_date"].strftime("%Y-%m-%d"),
                "schedule": schedule["schedule"].to_dict(orient="records")
            }
            for schedule in schedules
        ]
    }
    with open(DATA_FILE, "w") as file:
        json.dump(new_data, file, indent=4)
    print("Data saved successfully!")  # Debugging

# Function to load all data from a JSON file
def load_all_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as file:
            try:
                data = json.load(file)
                # Ensure all keys are present
                if "work_group" not in data:
                    data["work_group"] = []
                if "unavailabilities" not in data:
                    data["unavailabilities"] = {}
                if "schedules" not in data:
                    data["schedules"] = []

                # Convert string dates back to datetime objects
                data["unavailabilities"] = {
                    person: [(datetime.strptime(start, "%Y-%m-%d"), datetime.strptime(end, "%Y-%m-%d")) for start, end in unavails]
                    for person, unavails in data["unavailabilities"].items()
                }
                # Convert schedule dates back to datetime objects
                for schedule in data["schedules"]:
                    schedule["start_date"] = datetime.strptime(schedule["start_date"], "%Y-%m-%d")
                    schedule["end_date"] = datetime.strptime(schedule["end_date"], "%Y-%m-%d")
                    schedule["schedule"] = pd.DataFrame(schedule["schedule"])
                return data
            except json.JSONDecodeError:
                print("Error: JSON file is corrupted. Initializing with default data.")
                return {"work_group": [], "unavailabilities": {}, "schedules": []}
    return {"work_group": [], "unavailabilities": {}, "schedules": []}

# Load initial data
data = load_all_data()

# Function to generate pairs dynamically
def generate_pairs(group):
    return list(itertools.combinations(group, 2))
    
# Function for adding a person
def add_person_to_group(person):
    if person and person not in data["work_group"]:
        data["work_group"].append(person)
        data["unavailabilities"][person] = []
        save_all_data(data)  # Save changes
    return show_people()

# Function for removing a person
def remove_person_from_group(person):
    if person in data["work_group"]:
        data["work_group"].remove(person)
        del data["unavailabilities"][person]
        save_all_data(data)  # Save changes
    return show_people()

# Make sure show_people reflects the current state
def show_people():
    people_with_unavail = []
    for person in data["work_group"]:
        unavail_str = ", ".join([f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}" for start, end in data["unavailabilities"].get(person, [])])
        people_with_unavail.append({"Individuals": person, "Unavailability": unavail_str})
    return pd.DataFrame(people_with_unavail)

# Function to add unavailability
def add_unavailability(person, start_unaval, end_unaval):
    if person in data["work_group"]:
        start_unaval_date = datetime.fromtimestamp(start_unaval)
        end_unaval_date = datetime.fromtimestamp(end_unaval)
        if person not in data["unavailabilities"]:
            data["unavailabilities"][person] = []
        data["unavailabilities"][person].append((start_unaval_date, end_unaval_date))
        save_all_data(data)
    return show_people()
    
# Function to get Swedish national holidays for the next 10 years
def get_swedish_holidays():
    swedish_holidays = holidays.Sweden(years=range(datetime.now().year, datetime.now().year + 10))
    return set(swedish_holidays.keys())
    
# Function to remove unavailability
def remove_unavailability(person, start_unaval, end_unaval):
    if person in data["work_group"]:
        start_unaval_date = datetime.fromtimestamp(start_unaval)
        end_unaval_date = datetime.fromtimestamp(end_unaval)
        data["unavailabilities"][person] = [
            (start, end) for start, end in data["unavailabilities"][person]
            if not (start == start_unaval_date and end == end_unaval_date)
        ]
        save_all_data(data)
    return show_people()
    
import holidays
def generate_schedule(start_date, end_date):
    schedule = []

    # Convert timestamps to datetime objects if they are not already
    if isinstance(start_date, (int, float)):
        current_date = datetime.fromtimestamp(start_date)
    else:
        current_date = start_date

    if isinstance(end_date, (int, float)):
        end_date = datetime.fromtimestamp(end_date)

    # Get Swedish holidays
    swedish_holidays = get_swedish_holidays()

    shift_assignments = generate_pairs(data["work_group"])

    last_assigned = []  # Track individuals who worked the previous day

    while current_date <= end_date:
        if (current_date.weekday() < 5) and (current_date not in swedish_holidays):  # Only weekdays
            random.shuffle(shift_assignments)  # Shuffle pairs for randomness
            
            assigned_today = None

            for person1, person2 in shift_assignments:
                # Check availability
                if not (any(start <= current_date <= end for start, end in data["unavailabilities"].get(person1, [])) or
                        any(start <= current_date <= end for start, end in data["unavailabilities"].get(person2, []))):
                    
                    # Ensure that neither person worked the previous day
                    if person1 not in last_assigned and person2 not in last_assigned:
                        assigned_today = (person1, person2)
                        schedule.append({
                            "Date": current_date.strftime('%d %b %Y'),
                            "Day": current_date.strftime('%A'),
                            "Assigned": f"{person1}, {person2}"
                        })
                        last_assigned = [person1, person2]  # Update last assigned
                        break  # Exit the for loop once a valid pair is found

            # If no valid pair was found, we need to handle it.
            if assigned_today is None:
                last_assigned = []  # Reset last assigned if no pair could be assigned

        current_date += timedelta(days=1)

    # Group by week
    df_schedule = pd.DataFrame(schedule)
    df_schedule['Week'] = df_schedule['Date'].apply(lambda x: datetime.strptime(x, '%d %b %Y').isocalendar()[1])

    # Save the generated schedule
    data["schedules"].append({
        "start_date": current_date,  # This should still be a datetime object
        "end_date": end_date,         # This should also be a datetime object
        "schedule": df_schedule
    })
    save_all_data(data)
    
    return df_schedule

from openpyxl import Workbook
from openpyxl.styles import Border, Side, Alignment, Font

import pandas as pd
from openpyxl.styles import Border, Side, Alignment, Font
from openpyxl.utils.dataframe import dataframe_to_rows

def save_schedule(schedule_df):
    if schedule_df.empty:
        return "No schedule to save."

    # Create a new DataFrame for the formatted schedule
    formatted_schedule = []

    # Group by week
    for week, group in schedule_df.groupby("Week"):
        # Add week header
        formatted_schedule.append({"Week": week, "Monday": "", "Tuesday": "", "Wednesday": "", "Thursday": "", "Friday": ""})
        
        # Add dates for the week
        dates = group["Date"].tolist()
        formatted_schedule.append({
            "Week": "Main Schedule",
            "Monday": dates[0] if len(dates) > 0 else "",
            "Tuesday": dates[1] if len(dates) > 1 else "",
            "Wednesday": dates[2] if len(dates) > 2 else "",
            "Thursday": dates[3] if len(dates) > 3 else "",
            "Friday": dates[4] if len(dates) > 4 else ""
        })
        
        # Add shifts for the week
        shifts = group["Assigned"].tolist()
        formatted_schedule.append({
            "Week": "08 - 17.00",
            "Monday": shifts[0] if len(shifts) > 0 else "",
            "Tuesday": shifts[1] if len(shifts) > 1 else "",
            "Wednesday": shifts[2] if len(shifts) > 2 else "",
            "Thursday": shifts[3] if len(shifts) > 3 else "",
            "Friday": shifts[4] if len(shifts) > 4 else ""
        })
        
        # Add an empty row between weeks
        formatted_schedule.append({"Week": "", "Monday": "", "Tuesday": "", "Wednesday": "", "Thursday": "", "Friday": ""})

    # Convert the formatted schedule to a DataFrame
    formatted_df = pd.DataFrame(formatted_schedule)

    # Save to Excel using openpyxl for styling
    with pd.ExcelWriter("generated_schedule.xlsx", engine="openpyxl") as writer:
        formatted_df.to_excel(writer, index=False, sheet_name="Schedule")
        
        # Access the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets["Schedule"]
        
        # Define a border style
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )
        
        # Define alignment and font styles
        center_alignment = Alignment(horizontal="center", vertical="center")
        bold_font = Font(bold=True)
        
        # Apply styles to the "Week" column and other cells
        for row in worksheet.iter_rows(min_row=1, max_row=len(formatted_df), min_col=1, max_col=6):
            for cell in row:
                cell.border = thin_border
                cell.alignment = center_alignment
                if cell.row == 1 or cell.column == 1:  # Header row or "Week" column
                    cell.font = bold_font
        
        # Adjust column widths
        for col in worksheet.columns:
            max_length = 0
            column = col[0].column_letter  # Get the column name
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            worksheet.column_dimensions[column].width = adjusted_width

        # Add bounding boxes around each week's schedule
        start_row = 1
        for week, group in schedule_df.groupby("Week"):
            end_row = start_row + 3  # Each week's schedule spans 4 rows (header, dates, shifts, empty row)
            for row in worksheet.iter_rows(min_row=start_row, max_row=end_row, min_col=1, max_col=6):
                for cell in row:
                    cell.border = thin_border
            start_row = end_row + 1

    return "Schedule saved as 'generated_schedule.xlsx'."

# Function to save the schedule as an Excel file
def fetch_schedule():
    if data["schedules"]:
        return data["schedules"][-1]["schedule"]
    else:
        return df.Dataframe()

# Gradio interface
with gr.Blocks() as demo:
    gr.Markdown("# Automatic Schedule Generator")

    # Textboxes
    with gr.Row():
        start_date = gr.DateTime(label="Schedule Start Date", include_time=False)
        end_date = gr.DateTime(label="End Date", include_time=False)

    work_gp = gr.Dataframe(label="Work Group", value=show_people(), interactive=False)

    with gr.Row(scale=3):
        new_person = gr.Textbox(label="Add or Remove Individual to Work Group", scale=3)
        with gr.Column():
            add_person = gr.Button("Add")
            remove_person = gr.Button("Remove")

    with gr.Row():
        unaval_per = gr.Dropdown(label="Unavailability", choices=data["work_group"], interactive=True)
        start_unaval = gr.DateTime(label="Start Date", include_time=False)
        end_unaval = gr.DateTime(label="End Date", include_time=False)
        with gr.Column():
            add_unaval = gr.Button("Add Unavailability")
            remove_unaval = gr.Button("Remove Unavailability")

    generate_schedule_btn = gr.Button("Generate Schedule")

    # Output
    schedule_output = gr.Dataframe(label="Generated Schedule",value=fetch_schedule(), interactive=True)

    # Button functionalities
    add_person.click(fn=add_person_to_group, inputs=new_person, outputs=work_gp)
    remove_person.click(fn=remove_person_from_group, inputs=new_person, outputs=work_gp)
    add_unaval.click(fn=add_unavailability, inputs=[unaval_per, start_unaval, end_unaval], outputs=work_gp)
    remove_unaval.click(fn=remove_unavailability, inputs=[unaval_per, start_unaval, end_unaval], outputs=work_gp)
    generate_schedule_btn.click(fn=generate_schedule, inputs=[start_date, end_date], outputs=schedule_output)

    # Save Schedule Button
    save_schedule_btn = gr.Button("Save Schedule as Excel")
    output_message = gr.Textbox(label="Output Message", interactive=False)  # Message box for feedback
    save_schedule_btn.click(fn=save_schedule, inputs=schedule_output, outputs=output_message)

# Launch the app
demo.launch()


# In[ ]:




