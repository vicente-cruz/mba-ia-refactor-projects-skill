const express = require('express');
const { asyncHandler } = require('../middlewares/asyncHandler');

function checkoutRoutes(checkoutController) {
    const router = express.Router();
    router.post('/api/checkout', asyncHandler(async (req, res) => {
        res.status(200).json(await checkoutController.checkout(req.body));
    }));
    return router;
}

module.exports = { checkoutRoutes };
