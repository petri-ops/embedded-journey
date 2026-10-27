from .base import Feature


class LogFeature(Feature):
    id = "log"
    title = "数据日志"
    order = 60
    fields = [{"key": "log_rows", "label": "行数"}]
    card_fields = ["log_rows"]
    actions = [{"action": "now", "label": "记录一行", "type": "button", "on_card": False}]

    def status(self):
        return {"log_rows": self.app.log_rows}

    def command(self, action, value=None):
        if action == "now":
            self.app.log_row()
            return {"ok": True, "log_rows": self.app.log_rows}
        return {"ok": False, "error": "unsupported action"}
