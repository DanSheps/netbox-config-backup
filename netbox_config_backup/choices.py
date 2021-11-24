from utilities.choices import ChoiceSet


#
# File Types for Backup Files
#

class FileTypeChoices(ChoiceSet):

    TYPE_RUNNING = 'running'
    TYPE_STARTUP = 'startup'

    CHOICES = (
        (TYPE_RUNNING, 'Running'),
        (TYPE_STARTUP, 'Startup'),
    )

class CommitTreeChangeTypeChoices(ChoiceSet):

    TYPE_ADD = 'add'
    TYPE_MODIFY = 'modify'

    CHOICES = (
        (TYPE_ADD, 'Add'),
        (TYPE_MODIFY, 'Modify'),
    )

