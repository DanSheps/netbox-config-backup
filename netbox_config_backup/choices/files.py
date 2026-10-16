from utilities.choices import ChoiceSet

__all__ = ('FileTypeChoices',)


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
