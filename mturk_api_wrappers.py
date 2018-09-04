"""
MTurk API wrappers to deal with workers and HITs
"""


def approve_hits(mturk, hit_ids,
                 feedback_str="Thank you for completing our HIT! We have more image segmentation tasks available"):
    """Approve all submitted assignments for the HITs given, if not already approved or rejected"""
    all_assignments = []
    for hit in hit_ids:
        resp = mturk.list_assignments_for_hit(HITId=hit, AssignmentStatuses=['Submitted'])
        all_assignments.extend(a['AssignmentId'] for a in resp['Assignments'])
    approve_assignments(mturk, all_assignments, feedback_str)


def approve_assignments(mturk, assignment_ids, feedback_str):
    """Approve each assignment in the list if not already approved/rejected"""
    for assignment in assignment_ids:
        resp = mturk.get_assignment(AssignmentId=assignment)
        if resp['Assignment']['AssignmentStatus'] == "Approved" or resp['Assignment']['AssignmentStatus'] == "Rejected":
            continue
        resp = mturk.approve_assignment(AssignmentId=assignment, RequesterFeedback=feedback_str)
        print(assignment, resp)


def reject_assignments(mturk, assignment_ids, feedback_str):
    """Reject each assignment in the list if not already approved/rejected"""
    for assignment in assignment_ids:
        resp = mturk.get_assignment(AssignmentId=assignment)
        if resp['Assignment']['AssignmentStatus'] == "Approved" or resp['Assignment']['AssignmentStatus'] == "Rejected":
            continue
        resp = mturk.reject_assignment(AssignmentId=assignment, RequesterFeedback=feedback_str)
        print(assignment, resp)
    print(len(assignment_ids), "rejected")


def create_worker_exclusion_qualification(client):
    """Create a special qualification to exclude workers from some/all of our tasks
    without blocking completely (which can be problematic for their & our reputation)
    """
    client.create_qualification_type(Name="E-SEGMENTATION",
                                     Description="_",
                                     QualificationTypeStatus="Active",
                                     )


def apply_exclusion_qualification_to_worker(client, worker_id, qualification_type_id):
    """Silently block worker by giving them our Exclude qualification"""
    client.associate_qualification_with_worker(QualificationTypeId=qualification_type_id,
                                               WorkerId=worker_id,
                                               SendNotification=False)
