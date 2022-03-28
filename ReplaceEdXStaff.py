# VPAL Multi-course Staffing Script

import os
import csv
import sys
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

instructions = """
to run:
python3 ReplaceEdXStaff.py filename.csv

The csv file must have these headers/columns:
Course - course name or identifier (optional)
URL - the address of class' Course Team Settings page
Add - the e-mail addresses of the staff to be added. (not usernames)
      If there are multiple staff, space-separate them.
Remove - just like "Add".

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
    new_team_button = "a.create-user-button"
    new_staff_email_input = "input#user-email-input"
    add_user_button = "div.actions button.action-primary"
    # Removing staff
    staff_email_location = "span.user-email"
    remove_user_button = "a.remove-user"  # This will have data-id = the email address.

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
        access_success = False
        # Sign in
        driver.get(login_page)
        driver.find_elements(By.CSS_SELECTOR, username_input)
        driver.clear()
        driver.send_keys(username)
        driver.find_elements(By.CSS_SELECTOR, password_input)
        driver.clear()
        driver.send_keys(password)

        assert "Dashboard" in driver.title, "Could not log in or dashboard timed out."

        # if not access_success:
        #     skipped_classes.append(each_row)

        # For each line in the CSV...
        for each_row in reader:
            print(each_row)

            # Open the URL.
            # If we can't open the URL:
            # Make a note and skip this course.
            # Wait for load.
            # If we have people to add...
            # Split the Add string by spaces
            # For each Add address:
            # Click the "New Team Member" button
            # Put the e-mail into the input box
            # Click "Add User"
            # Wait for load.
            # If there's an error message:
            # Make a note and move on.
            # Otherwise
            # Remove that e-mail address from the Add list in the new dict.
            # If we have people to remove...
            # Split the Remove string by spaces
            # For each Remove address:
            # Find the e-mail address on the page.
            # Click the trash can ("remove user" button)
            # Wait for load.
            # If there's an error message:
            # Make a note and move on.
            # Otherwise
            # Remove that e-mail address from the Remove list in the new dict.

    # Write out a new csv with the ones we couldn't do.
    """
    with open("remaining_courses.csv", "w", newline="") as remaining_courses:
        fieldnames = ["Course", "URL", "Add", "Remove"]
        writer = csv.DictWriter(remaining_courses, fieldnames=fieldnames)

        writer.writeheader()
        for x in skipped_classes:
            writer.writerow(x)
    """

    # Done.
    driver.quit()


if __name__ == "__main__":
    ReplaceEdXStaff()
