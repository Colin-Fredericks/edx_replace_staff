# VPAL Multi-course Staffing Script

import os
import csv
import sys
import argparse
from getpass import getpass
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


def setUpWebdriver():
    # Instantiating a headless Chrome browser
    print("Setting up webdriver.")
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + "."
    c = Options()
    # c.add_argument("--headless")
    driver = webdriver.Chrome(options=c)
    driver.implicitly_wait(10)
    return driver


def signIn(driver, username, password):

    # Locations
    login_page = "https://authn.edx.org/login"
    username_input_css = "#emailOrUsername"
    password_input_css = "#password"
    login_button_css = ".login-button-width"

    # Open the edX sign-in page
    print("Logging in...")
    driver.get(login_page)

    # Sign in
    username_field = driver.find_elements(By.CSS_SELECTOR, username_input_css)[0]
    username_field.clear()
    username_field.send_keys(username)
    password_field = driver.find_elements(By.CSS_SELECTOR, password_input_css)[0]
    password_field.clear()
    password_field.send_keys(password)
    login_button = driver.find_elements(By.CSS_SELECTOR, login_button_css)[0]
    login_button.click()

    # Check to make sure we're signed in
    try:
        element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "my-courses"))
        )
    except:
        assert (
            "Dashboard" in driver.title
        ), "Could not log into edX or course dashboard page timed out."

    print("Logged in.")
    return


def addStaff(driver, email_list):

    # Locations for add-staff inputs
    new_team_css = "a.create-user-button"
    new_staff_email_css = "input#user-email-input"
    add_user_css = "div.actions button.action-primary"

    # For each address:
    for email in email_list:
        print("Adding " + email)
        # Click the "New Team Member" button
        new_team_button = driver.find_elements(By.CSS_SELECTOR, new_team_css)[0]
        new_team_button.click()
        # Put the e-mail into the input box
        email_box = driver.find_elements(By.CSS_SELECTOR, new_staff_email_css)[0]
        email_box.clear()
        email_box.send_keys(email)
        # Click "Add User"
        add_user_button = driver.find_elements(By.CSS_SELECTOR, add_user_css)[0]
        add_user_button.click()

        # If there's an error message, it's fine. Click the "ok" button.
        wrong_email_css = "#prompt-error.is-shown"
        already_on_team_css = "#prompt-warning.is-shown"
        ok_button_css = "button.action-primary"

        # TODO: This part isn't working. Not sure why.
        if len(driver.find_elements(By.CSS_SELECTOR, wrong_email_css)) > 0:
            ok_button = driver.findElements(
                By.CSS_SELECTOR, wrong_email + " " + ok_button_css
            )
            print(email + " could not be found.")
        if len(driver.find_elements(By.CSS_SELECTOR, already_on_team_css)) > 0:
            ok_button = driver.findElements(
                By.CSS_SELECTOR, already_on_team + " " + ok_button_css
            )
            print(email + " is already on the team.")

    return


def promoteStaff(driver, email_list):
    return


def removeStaff(driver, email_list):

    # Locations for remove-staff inputs
    # This will be inside an LI with data-email equal to the user's email address
    remove_user_css = "a.remove-user"
    confirm_removal_css = "#prompt-warning.is-shown button.action-primary"

    # For each address:
    for email in email_list:
        print("Finding " + email)
        # Click the trash can ("remove user" button)
        # E-mails in the data attribute are lowercased.
        remove_button = driver.find_elements(
            By.CSS_SELECTOR, "li[data-email='" + email.lower() + "'] " + remove_user_css
        )
        if len(remove_button) > 0:
            remove_button[0].click()
            # Click the "confirm" button.
            print("Removing " + email)
            driver.find_elements(By.CSS_SELECTOR, confirm_removal_css)[0].click()
            # try:
            #     element = WebDriverWait(driver, 5).until(
            #         EC.presence_of_element_located((By.ID, confirm_removal_css))
            #     )
            # except:
            #     ## TODO: This is firing when it shouldn't.
            #     print("Could not find OK button for removal.")
            # finally:
            #     print("Removing " + email)
            #     driver.find_elements(By.CSS_SELECTOR, confirm_removal_css)[0].click()
        else:
            # If we can't find the e-mail address, they weren't in the class anyway.
            print(email + " was not in this course.")

    return


def demoteStaff(driver, email_list):
    return


#######################
# Main starts here
#######################


def ReplaceEdXStaff():

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
    password = getpass()

    # Prep the web driver and sign into edX.
    driver = setUpWebdriver()
    signIn(driver, username, password)

    # Open the csv and read it to a set of dicts
    with open(args.csvfile, "r") as file:
        print("Opening csv file.")
        reader = csv.DictReader(file)

        # For each line in the CSV...
        for each_row in reader:
            print("Processing line:")
            print(each_row)
            num_classes = num_classes + 1

            # Open the URL.
            driver.get(each_row["URL"])

            # Wait for the page to load.
            try:
                new_team_css = "a.create-user-button"
                element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, new_team_css))
                )
            except:
                # If we can't open the URL, make a note and skip this course.
                skipped_classes.append(each_row)
                if "Forbidden" in driver.title:
                    print("Could not open course " + each_row["URL"])
                if "Dashboard" in driver.title:
                    print("Course load timed out.")
                continue

            # Functions to call for each task:
            jobs = {
                "Add": addStaff,
                "Promote": promoteStaff,
                "Remove": removeStaff,
                "Demote": demoteStaff,
            }
            for j in jobs:
                # Taking out whitespace.
                # Split e-mail list on spaces and throw out blank elements.
                # print(j + ": " + each_row[j])
                email_list_with_blanks = each_row[j].split(" ")
                email_list = [x for x in email_list_with_blanks if x != ""]
                if len(each_row[j]) > 0:
                    jobs[j](driver, email_list)

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
                fieldnames = ["Course", "URL", "Add", "Promote", "Remove", "Demote"]
                writer = csv.DictWriter(remaining_courses, fieldnames=fieldnames)

                writer.writeheader()
                for x in skipped_classes:
                    writer.writerow(x)
        else:
            print("Successful in all " + str(num_classes) + " courses.")

    # Done.
    driver.quit()


if __name__ == "__main__":
    ReplaceEdXStaff()
