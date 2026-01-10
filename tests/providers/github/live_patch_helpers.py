from otterdog.models import LivePatch, LivePatchContext, ModelObject


def determine_model_object(
    a: ModelObject | None,
    b: ModelObject | None,
) -> type[ModelObject]:
    """
    Determine the model object type from the given objects.

    At least one of a or b must be not None.
    If both are provided, they must be of the same type.
    """
    if a and b:
        assert type(a) == type(b), "Both objects must be of the same type"  # noqa: E721
        return type(a)
    elif a:
        return type(a)
    elif b:
        return type(b)
    else:
        raise ValueError("At least one of a or b must be provided")


def generate_live_patch(
    old: ModelObject | None,
    new: ModelObject | None,
    parent_object: ModelObject | None,
    context: LivePatchContext,
) -> LivePatch:
    """Generate exactly one LivePatch for a given model class.

    Collects the patch by calling model_cls.generate_live_patch and ensures exactly one is produced.

    !old & new => Create
    old & new => Update
    old & !new => Delete
    """
    model_cls = determine_model_object(old, new)

    patches: list[LivePatch] = []
    model_cls.generate_live_patch(
        expected_object=new,
        current_object=old,
        parent_object=parent_object,
        context=context,
        handler=lambda p: patches.append(p),  # pyright: ignore[reportArgumentType]
    )
    assert len(patches) == 1, f"Expected exactly one patch, got {len(patches)}"
    return patches[0]
