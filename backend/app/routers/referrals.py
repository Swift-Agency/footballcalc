"""
Referral system router.
The main referral endpoints (claim, me) live in billing.py for simplicity.
This module re-exports the billing router to keep main.py clean,
or can be used for additional referral-specific endpoints.
"""
from fastapi import APIRouter

router = APIRouter()
# All referral endpoints are included in billing.router (/referrals/claim, /referrals/me).
# This file is a placeholder so main.py import doesn't break if billing is split later.
