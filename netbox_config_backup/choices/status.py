from utilities.choices import ChoiceSet

__all__ = ('StatusChoices',)


class StatusChoices(ChoiceSet):
    STATUS_ACTIVE = 'active'
    STATUS_DISABLED = 'disabled'

    CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DISABLED, 'Disabled'),
    )
