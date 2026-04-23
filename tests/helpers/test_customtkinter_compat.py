from modules.helpers.customtkinter_compat import apply_ctk_button_after_cleanup_patch


class _FakeButton:
    def __init__(self):
        self.after_calls = []
        self.after_cancel_calls = []
        self.destroy_calls = 0

    def after(self, ms, callback=None, *args):
        callback_id = f"after-{len(self.after_calls) + 1}"
        self.after_calls.append((ms, callback, args, callback_id))
        return callback_id

    def after_cancel(self, callback_id):
        self.after_cancel_calls.append(callback_id)

    def destroy(self):
        self.destroy_calls += 1
        return "destroyed"


class _FakeCTK:
    CTkButton = _FakeButton


def test_patch_cancels_pending_after_callbacks_on_destroy():
    apply_ctk_button_after_cleanup_patch(_FakeCTK)

    button = _FakeCTK.CTkButton()
    callback_id_1 = button.after(40, lambda: None)
    callback_id_2 = button.after(10, lambda: None)

    result = button.destroy()

    assert result == "destroyed"
    assert button.destroy_calls == 1
    assert callback_id_1 in button.after_cancel_calls
    assert callback_id_2 in button.after_cancel_calls


def test_patch_is_idempotent():
    apply_ctk_button_after_cleanup_patch(_FakeCTK)
    apply_ctk_button_after_cleanup_patch(_FakeCTK)

    button = _FakeCTK.CTkButton()
    callback_id = button.after(5, lambda: None)
    button.after_cancel(callback_id)

    assert button.after_cancel_calls.count(callback_id) == 1
