orderchoices = [("Pending", "Pending"), ("Close", "Close")]

jobchoices = [("Pending", "Pending"),
              ("Close", "Close"),
              ("Unplanned", "Unplanned"),
              ("Completed", "Completed"),
              ("Cancelled", "Cancelled"),
              ("Hold", "Hold"),
              ("Partially Ready", "Partially Ready"),
              ("Job Work", "Job Work"),
              ("Account clearance","Account clearance")
              ]

SUPPLY_CHOICES = [('ROLL', 'ROLL'), ('POUCH', 'POUCH')]
DIRECTION = [('ANY', 'ANY'), ('READABLE', 'READABLE'), ('UNREADABLE', 'UNREADABLE')]

processchoices = [("Pending", "Pending"), ("Completed", "Completed"), ("Incomplete", "Incomplete"),
                  ("Running", "Running")]
cylinderchoices = [(None,"blank" ),('Available', 'Available'),
                   ('Not Applicable', 'Not Applicable'),
                   ('Sent For Repairing', 'Sent For Repairing'),
                   ('Returned To Customer', 'Returned To Customer'),
                   ('Not Available', 'Not Available')]
