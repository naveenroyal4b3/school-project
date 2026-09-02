"""Per-tenant branding and vocabulary.

One deployment serves schools, colleges, universities, coaching centres and
training institutes. They do not use the same words for the same things: a
school has classes and parents, a coaching centre has batches and guardians,
and calling a college lecturer a "teacher" reads as wrong to its own staff.

Rather than scatter conditionals through the templates, each organization type
maps to a vocabulary that the front end reads once and applies to its labels.
"""

DEFAULT_VOCABULARY = {
    "organization": "Institution",
    "faculty": "Faculty",
    "faculty_plural": "Faculty",
    "class_group": "Class",
    "class_group_plural": "Classes",
    "guardian": "Guardian",
    "guardian_plural": "Guardians",
    "admission_no": "Admission no.",
    "campus": "Campus",
}

VOCABULARIES = {
    "School": {
        "organization": "School",
        "faculty": "Teacher",
        "faculty_plural": "Teachers",
        "class_group": "Class",
        "class_group_plural": "Classes",
        "guardian": "Parent",
        "guardian_plural": "Parents",
        "admission_no": "Admission no.",
        "campus": "School",
    },
    "College": {
        "organization": "College",
        "faculty": "Lecturer",
        "faculty_plural": "Faculty",
        "class_group": "Course",
        "class_group_plural": "Courses",
        "guardian": "Guardian",
        "guardian_plural": "Guardians",
        "admission_no": "Enrolment no.",
        "campus": "Campus",
    },
    "University": {
        "organization": "University",
        "faculty": "Professor",
        "faculty_plural": "Faculty",
        "class_group": "Programme",
        "class_group_plural": "Programmes",
        "guardian": "Guardian",
        "guardian_plural": "Guardians",
        "admission_no": "Registration no.",
        "campus": "Campus",
    },
    "Coaching Center": {
        "organization": "Centre",
        "faculty": "Trainer",
        "faculty_plural": "Trainers",
        "class_group": "Batch",
        "class_group_plural": "Batches",
        "guardian": "Guardian",
        "guardian_plural": "Guardians",
        "admission_no": "Enrolment no.",
        "campus": "Centre",
    },
    "Training Institute": {
        "organization": "Institute",
        "faculty": "Trainer",
        "faculty_plural": "Trainers",
        "class_group": "Batch",
        "class_group_plural": "Batches",
        "guardian": "Guardian",
        "guardian_plural": "Guardians",
        "admission_no": "Enrolment no.",
        "campus": "Institute",
    },
}


def vocabulary_for(organization_type):
    """Labels for one organization type, falling back to neutral wording.

    An unrecognised type returns the neutral set rather than raising: a tenant
    with an unexpected type should see slightly generic labels, not an error
    page.
    """
    return VOCABULARIES.get(organization_type, DEFAULT_VOCABULARY)
