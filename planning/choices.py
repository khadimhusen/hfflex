PROCESS_STATUS = [("Pending", "Pending"),
                  ("Completed", "Completed"),
                  ("Running", "Running"),
                  ("Hold","Hold")]

SCHEDULE_TYPE = [
        ('Production', 'Production'),
        ('Idle', 'Idle'),
    ]
IDLE_TYPE = [
        ('Planned', 'Planned'),
        ('Unplanned', 'Unplanned'),
    ]

MATERIAL_STATUS = [("Not Available","Not Available"),("Available","Available")]


HOLD_STATUSES    = {'Hold', 'Unplanned', 'Cancelled', 'Account clearance'}
RELEASE_STATUSES = {'Pending', 'Partially ready', 'Job Work'}

