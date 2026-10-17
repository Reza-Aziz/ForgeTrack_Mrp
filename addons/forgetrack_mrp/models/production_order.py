from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class ProductionOrder(models.Model):
    _name = "forgetrack.production.order"
    _description = "ForgeTrack Production Order"
    _order = "id desc"

    name = fields.Char(
        string="Order Reference",
        required=True,
        default="New",
    )

    product_name = fields.Char(
        string="Product",
        required=True,
    )

    quantity = fields.Integer(
        string="Quantity",
        required=True,
        default=1,
    )

#ini kurang paham
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("done", "Done"),
        ],
        string="Status",
        default="draft",
        required=True,
        copy=False,
    )

    notes = fields.Text(string="Notes")

    @api.constrains("quantity")
    def _check_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(
                    "Production quantity must be greater than zero."
                )
    def action_confirm(self):
        for record in self:
            if record.state != "draft":
                raise UserError(
                    "Only draft orders can be confirmed."
                )
            record.state="confirmed"

    def action_done(self):
        for record in self:
            if record.state != "confirmed":
                raise UserError (
                    "Only confirmed orders can be completed."
                )
            record.state="done"
            