const express = require('express');
const { asyncHandler } = require('../middlewares/asyncHandler');
const { requireAdminToken } = require('../middlewares/requireAdminToken');

function adminRoutes(reportController, adminToken) {
    const router = express.Router();
    router.get('/api/admin/financial-report', requireAdminToken(adminToken), asyncHandler(async (req, res) => {
        res.json(await reportController.financialReport());
    }));
    return router;
}

module.exports = { adminRoutes };
