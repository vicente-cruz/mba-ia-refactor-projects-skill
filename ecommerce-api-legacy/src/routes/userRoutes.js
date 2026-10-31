const express = require('express');
const { asyncHandler } = require('../middlewares/asyncHandler');
const { requireAdminToken } = require('../middlewares/requireAdminToken');

function userRoutes(userController, adminToken) {
    const router = express.Router();
    router.delete('/api/users/:id', requireAdminToken(adminToken), asyncHandler(async (req, res) => {
        res.send(await userController.deleteUser(req.params.id));
    }));
    return router;
}

module.exports = { userRoutes };
