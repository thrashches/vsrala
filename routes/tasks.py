from __future__ import annotations

import logging

from celery import shared_task

from .models import Route
from . import surface as surface_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def enrich_route_surfaces(self, route_id: int) -> dict:
    try:
        route = Route.objects.get(pk=route_id)
    except Route.DoesNotExist:
        return {'ok': False, 'error': 'route_not_found'}

    route.surface_status = Route.SurfaceStatus.PENDING
    route.save(update_fields=['surface_status', 'updated_at'])

    try:
        surface_service.enrich_route(route)
        return {
            'ok': True,
            'status': route.surface_status,
            'segments': len(route.surface_segments or []),
        }
    except Exception as exc:
        logger.exception('Overpass enrichment failed for route %s', route_id)
        route.surface_status = Route.SurfaceStatus.FAILED
        route.surface_segments = []
        route.save(update_fields=['surface_status', 'surface_segments', 'updated_at'])
        raise self.retry(exc=exc)
