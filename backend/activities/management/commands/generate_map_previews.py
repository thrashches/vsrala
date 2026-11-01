from django.core.management.base import BaseCommand
from django.db.models import Q

from activities.map_preview import apply_map_preview
from activities.models import Activity


class Command(BaseCommand):
    help = 'Generate map_preview images for activities that have track_points but no preview'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate previews even when map_preview already exists',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Max number of activities to process (0 = all)',
        )

    def handle(self, *args, **options):
        qs = Activity.objects.exclude(
            Q(track_points__isnull=True) | Q(track_points=[]),
        ).order_by('pk')
        if not options['force']:
            qs = qs.filter(Q(map_preview='') | Q(map_preview__isnull=True))

        limit = options['limit']
        if limit > 0:
            qs = qs[:limit]

        total = 0
        ok = 0
        for activity in qs.iterator():
            total += 1
            if apply_map_preview(activity):
                ok += 1
                self.stdout.write(f'OK {activity.pk}')
            else:
                self.stdout.write(f'SKIP {activity.pk}')

        self.stdout.write(self.style.SUCCESS(f'Done: {ok}/{total} previews'))
