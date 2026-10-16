from utilities.choices import ChoiceSet

__all__ = ('CommitTreeChangeTypeChoices',)


class CommitTreeChangeTypeChoices(ChoiceSet):

    TYPE_ADD = 'add'
    TYPE_MODIFY = 'modify'

    CHOICES = (
        (TYPE_ADD, 'Add'),
        (TYPE_MODIFY, 'Modify'),
    )
