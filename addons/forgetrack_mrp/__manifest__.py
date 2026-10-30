{
    "name": "ForgeTrack MRP",
    "version": "19.0.1.0.0",
    "author": "Reza Aziz Simatupang",
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
    "assets": {
        "web.assets_backend": [
            "forgetrack_mrp/static/src/dashboard/dashboard.scss",
            "forgetrack_mrp/static/src/dashboard/dashboard.xml",
            "forgetrack_mrp/static/src/dashboard/dashboard.js",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}