# VPAL Multi-course Staffing Script

import os
import csv
import sys
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

instructions = """
to run:
python3 ReplaceEdXStaff.py filename.csv

The csv file must have these headers/columns:
Course - course name or identifier (optional)
URL - the address of class' Course Team Settings page
Add - the e-mail addresses of the staff to be added. (not usernames)
      If there are multiple staff, space-separate them.
Promote - promote these people to Admin status
Remove - just like "Add"
Demote - removes Admin status

The output is another CSV file that shows which courses couldn't be accessed
and which people couldn't be removed.
"""

#######################
# Main starts here
#######################


def ReplaceEdXStaff():

    # Current locations of items in edX:
    # Logging in
    login_page = "https://authn.edx.org/login"
    username_input = "#emailOrUsername"
    password_input = "#password"
    login_button = ".login-button-width"
    # Adding staff
    new_team_css = "a.create-user-button"
    new_staff_email_css = "input#user-email-input"
    add_user_css = "div.actions button.action-primary"
    # Removing staff
    staff_email_location = "span.user-email"
    remove_user_css = "a.remove-user"  # This will have data-id = the email address.

    num_classes = 0
    num_classes_fixed = 0
    skipped_classes = []
    unfound_addresses = []

    # Read in command line arguments.
    parser = argparse.ArgumentParser(usage=instructions, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("csvfile", default=None)

    args = parser.parse_args()
    if args.help or args.csvfile is None:
        sys.exit(instructions)

    if not os.path.exists(args.csvfile):
        sys.exit("Input file not found: " + args.csvfile)

    # Prompt for username and password
    print(
        """
This script requires a username and password to run.
This user must have Admin status on all courses in which
the script is to run. Press control-C to cancel.
"""
    )
    username = input("Username: ")
    password = input("Password: ")

    # Instantiating a headless Chrome browser
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + "."
    c = Options()
    c.add_argument("--headless")
    driver = webdriver.Chrome(options=c)
    driver.implicitly_wait(5)

    # Open the csv and read it to a set of dicts
    with open(args.csvfile, "r") as file:
        reader = csv.DictReader(file)

        # Open the edX sign-in page
        driver.get(login_page)

        # Sign in
        driver.find_elements(By.CSS_SELECTOR, username_input)
        driver.clear()
        driver.send_keys(username)
        driver.find_elements(By.CSS_SELECTOR, password_input)
        driver.clear()
        driver.send_keys(password)

        # Check to make sure we're signed in
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "my-courses"))
            )
        except:
            assert (
                "Dashboard" in driver.title
            ), "Could not log into edX or course dashboard page timed out."

        # For each line in the CSV...
        for each_row in reader:
            print(each_row)

            # Open the URL.
            driver.get(each_row["URL"])

            # Wait for the page to load.
            try:
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, new_team_css))
                )
            except:
                # If we can't open the URL, make a note and skip this course.
                skipped_classes.append(each_row)
                assert (
                    "Dashboard" in driver.title
                ), "Could not log in or dashboard timed out."

            # If we have people to add...
            if len(each_row["Add"]) > 0:
                to_add = each_row["Add"].split(" ")
                # For each Add address:
                for email in to_add:
                    # Click the "New Team Member" button
                    new_team_button = driver.find_elements(
                        by.CSS_SELECTOR, new_team_css
                    )
                    new_team_button.click()
                    # Put the e-mail into the input box
                    email_box = driver.find_elements(
                        by.CSS_SELECTOR, new_staff_email_css
                    )
                    email_box.clear()
                    email_box.keys(email)
                    # Click "Add User"
                    add_user_button = driver.find_elements(
                        by.CSS_SELECTOR, add_user_css
                    )
                    add_user_button.click()
                    pass

                # If there's an error message:
                #   Wrong e-mail address:
                #     wrong_email = "#prompt-error.is-shown"
                #   Already on course team:
                #     already_on_team = "#prompt-warning.is-shown"
                #   Click the ".action-primary" button in that div to say "ok"

                # If we have people to remove...
                # Split the Remove string by spaces
                # For each Remove address:
                # Find the e-mail address on the page.
                # If you can find it:
                # Click the trash can ("remove user" button)
                # Click the ".action-primary" button inside "#prompt-warning.is-shown"
                # If we can't find the e-mail address, no one cares.
                # Make a note and move on.
                # Otherwise
                # Remove that e-mail address from the Remove list in the new dict.

                # Promote/demote have no confirm buttons.
                # If we have people to promote...
                #   Split the Promote string by spaces
                #   For each Promote address:
                #     Find the li with data-email matching this one.
                #     Click the ".make-instructor.admin-role.add-admin-role" link
                # If we have people to demote...
                #   Split the Demote string by spaces
                #   For each Demote address:
                #     Find the li with data-email matching this one.
                #     Click the ".make-staff.admin-role.remove-admin-role" link

        # Write out a new csv with the ones we couldn't do.
        if len(skipped_classes) > 0:
            with open("remaining_courses.csv", "w", newline="") as remaining_courses:
                fieldnames = ["Course", "URL", "Add", "Remove"]
                writer = csv.DictWriter(remaining_courses, fieldnames=fieldnames)

                writer.writeheader()
                for x in skipped_classes:
                    writer.writerow(x)
        else:
            print("Successful in all " + str(len(reader)) + "courses.")

    # Done.
    driver.quit()


if __name__ == "__main__":
    ReplaceEdXStaff()
