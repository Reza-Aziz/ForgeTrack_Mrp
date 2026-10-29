{
    "name": "ForgeTrack MRP",
    "version": "19.0.1.0.0",
    "summary": "Simple manufacturing order management",
    "description": """
        A beginner custom module for managing
        simple production orders.
    """,
    "category": "Manufacturing",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/production_order_views.xml",
        "views/machine_reading_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}