#!/usr/bin/env python3
# VPAL Multi-course Staffing Script

import os
import csv
import sys
import time
import argparse
from getpass import getpass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# TODO: Better tracking of what we had to skip.
# TODO: Handle errors on add

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


# Instantiating a headless Chrome browser
def setUpWebdriver():
    print("Setting up webdriver.")
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + "."
    c = Options()
    # c.add_argument("--headless")
    driver = webdriver.Chrome(options=c)
    driver.implicitly_wait(2)
    return driver


def userIsPresent(driver, email):
    user_present_css = "li[data-email='" + email.lower() + "']"
    user_present = driver.find_elements(By.CSS_SELECTOR, user_present_css)
    if len(user_present) > 0:
        return True
    else:
        return False


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
        found_dashboard = WebDriverWait(driver, 10).until(
            EC.title_contains("Dashboard")
        )
    except:
        driver.close()
        if "Forbidden" in driver.title:
            sys.exit("403: Forbidden")
        if "Login" in driver.title:
            sys.exit("Took too long to log in.")
        sys.exit("Could not log into edX or course dashboard page timed out.")

    print("Logged in.")
    return


def addStaff(driver, email_list):

    # Locations for add-staff inputs
    wrong_email_css = "#prompt-error.is-shown button.action-primary"
    new_team_css = "a.create-user-button"
    new_staff_email_css = "input#user-email-input"
    add_user_css = "div.actions button.action-primary"

    # For each address:
    for email in email_list:
        success = False

        # If the user is already present, move to the next e-mail address.
        if userIsPresent(driver, email) > 0:
            print(email + " is already on course team.")
            continue

        # Retry up to 3 times.
        for x in range(0, 3):
            print("Adding " + email)

            # Try to find the "ok" button for the error dialogs.
            wrong_email_ok_button = driver.find_elements(
                By.CSS_SELECTOR, wrong_email_css
            )
            # If there is an error dialog open, report why, clear it, and move on.
            if len(wrong_email_ok_button) > 0:
                print("error dialog open")
                try:
                    print("No edX user with email " + email)
                    wrong_email_ok_button[0].click()
                    # Move to the next e-mail address.
                    success = True
                    break

                except Exception as e:
                    print("Couldn't click dialog, trying again...")
                    # print(repr(e))
                    # Give it another shot, sometimes delaying helps.
                    continue

            # If there isn't a dialog open, try to add the team member.
            else:
                # print("No error dialog")
                try:
                    # Click the "New Team Member" button
                    # print("click new team")
                    new_team_buttons = driver.find_elements(
                        By.CSS_SELECTOR, new_team_css
                    )
                    new_team_buttons[0].click()
                    # Put the e-mail into the input box.
                    # print("enter email")
                    email_boxes = driver.find_elements(
                        By.CSS_SELECTOR, new_staff_email_css
                    )
                    email_boxes[0].clear()
                    email_boxes[0].send_keys(email)
                    # Click "Add User"
                    # print("click add user")
                    add_user_buttons = driver.find_elements(
                        By.CSS_SELECTOR, add_user_css
                    )
                    add_user_buttons[0].click()
                    # If they've been successfully added, move on to the next e-mail.
                    if userIsPresent(driver, email):
                        success = True
                        break

                except Exception as e:
                    print("Couldn't add " + email + ", trying again...")
                    # print(repr(e))
                    # Give it another shot, sometimes delaying helps.
                    continue

        if success:
            print("Added " + email)
        else:
            print("Wasn't able to add " + email)

    return


def promoteStaff(driver, email_list):
    # For each address:
    for email in email_list:

        # Keep trying up to 3 times.
        if userIsPresent(driver, email):
            # Find the promotion button for this user.
            promotion_css = (
                "li[data-email='"
                + email.lower()
                + "'] a.make-instructor.admin-role.add-admin-role"
            )
            for x in range(0, 3):
                print("Promoting " + email)
                try:
                    # Click the "New Team Member" button
                    promotion_button = driver.find_elements(
                        By.CSS_SELECTOR, promotion_css
                    )
                    promotion_button[0].click()
                    break
                except Exception as e:
                    # print(repr(e))
                    print("Trying again...")

    return


def removeStaff(driver, email_list):

    # The "remove" button is a link inside an LI.
    # The LI has data-email equal to the user's email address.
    trash_can_css = "a.remove-user"
    confirm_removal_css = "#prompt-warning.is-shown button.action-primary"

    # For each address:
    for email in email_list:
        removal_button_css = "li[data-email='" + email.lower() + "'] " + trash_can_css

        # If this user isn't present, move on to the next one.
        if not userIsPresent(driver, email):
            print(email + " was already not in this course.")
            continue

        for x in range(0, 3):
            try:
                # E-mail addresses in the data attribute are lowercased.
                remove_button = driver.find_elements(
                    By.CSS_SELECTOR, removal_button_css
                )
                # Click the trash can ("remove user" button)
                remove_button[0].click()
                # Click the "confirm" button.
                print("Removing " + email)
                confirm_button = driver.find_elements(
                    By.CSS_SELECTOR, confirm_removal_css
                )
                confirm_button[0].click()
                break

            except Exception as e:
                # print(repr(e))
                # Keep trying up to 3 times.
                print("Trying again...")

    return


def demoteStaff(driver, email_list):
    # For each address:
    for email in email_list:
        # Find the demotion button for this user.
        demotion_css = (
            "li[data-email='"
            + email.lower()
            + "'] a.make-staff.admin-role.remove-admin-role"
        )

        for x in range(0, 3):
            print("Demoting " + email)
            try:
                # Click the "New Team Member" button
                demotion_button = driver.find_elements(By.CSS_SELECTOR, demotion_css)
                demotion_button[0].click()
                break
            except Exception as e:
                # print(repr(e))
                # Keep trying up to 3 times.
                print("Trying again...")

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
            # print("Processing line:")
            # print(each_row)
            num_classes += 1

            # Open the URL.
            driver.get(each_row["URL"].strip())

            # Check to make sure we've opened a new page.
            # The e-mail input box should be invisible.
            try:
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located(
                        (By.CSS_SELECTOR, "input#user-email-input")
                    )
                )
            except Exception as e:
                # print(repr(e))
                # If we can't open the URL, make a note and skip this course.
                skipped_classes.append(each_row)
                if "Forbidden" in driver.title:
                    print("Could not open course " + each_row["URL"])
                if "Dashboard" in driver.title:
                    print("Course Team page load timed out.")
                continue

            print(driver.title)
            # Functions to call for each task. As of Python 3.6 they'll stay in this order.
            jobs = {
                "Add": addStaff,
                "Promote": promoteStaff,
                "Remove": removeStaff,
                "Demote": demoteStaff,
            }
            for j in jobs:
                # Taking out whitespace.
                # Split e-mail list on spaces and throw out blank elements.
                email_list_with_blanks = each_row[j].split(" ")
                email_list = [x for x in email_list_with_blanks if x != ""]
                if len(each_row[j]) > 0:
                    jobs[j](driver, email_list)
                    # You have to wait because I don't even know why.
                    # Otherwise it skips lines - sometimes up to half of them.
                    time.sleep(2)

        # Write out a new csv with the ones we couldn't do.
        if len(skipped_classes) > 0:
            with open("remaining_courses.csv", "w", newline="") as remaining_courses:
                fieldnames = ["Course", "URL", "Add", "Promote", "Remove", "Demote"]
                writer = csv.DictWriter(remaining_courses, fieldnames=fieldnames)

                writer.writeheader()
                for x in skipped_classes:
                    writer.writerow(x)
        else:
            print("Total: " + str(num_classes) + " courses.")

    # Done.
    driver.quit()


if __name__ == "__main__":
    ReplaceEdXStaff()
