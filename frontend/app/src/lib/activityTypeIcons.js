const SLUG_ICONS = {
  road_cycling: 'directions_bike',
  mtb: 'directions_bike',
  gravel: 'directions_bike',
  track_cycling: 'directions_bike',
  running: 'directions_run',
  swimming: 'pool',
  walking: 'directions_walk',
  skiing: 'downhill_skiing',
  rowing: 'rowing',
}

export function activityTypeIcon(slug) {
  if (!slug) return 'fitness_center'
  return SLUG_ICONS[slug] || 'fitness_center'
}
