export function Skeleton({ className = '' }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />
}

export function ButtonSpinner({ className = '' }) {
  return <span className={`btn-spinner ${className}`} aria-hidden="true" />
}

export function ActivityCardSkeleton() {
  return (
    <article className="relative rounded bg-white shadow-card" aria-hidden="true">
      <div className="flex items-start gap-3 px-4 pt-4">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-48" />
        </div>
      </div>
      <div className="space-y-2 px-4 pt-3">
        <Skeleton className="h-5 w-64 max-w-full" />
        <Skeleton className="h-3 w-full max-w-sm" />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 px-4 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="space-y-1.5">
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-6 w-16" />
          </div>
        ))}
      </div>
      <Skeleton className="mt-4 h-52 w-full rounded-none" />
      <div className="flex items-center gap-3 border-t border-gray-100 px-4 py-3">
        <Skeleton className="h-7 w-16 rounded-full" />
        <Skeleton className="h-7 w-16 rounded-full" />
        <Skeleton className="ml-auto h-7 w-12 rounded-full" />
      </div>
    </article>
  )
}

export function ActivityDetailSkeleton() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6" aria-hidden="true">
      <div className="relative rounded bg-white shadow-card">
        <div className="border-b border-gray-100 px-5 py-4">
          <div className="flex items-start gap-3">
            <Skeleton className="h-12 w-12 rounded-full" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-3 w-56" />
              <Skeleton className="mt-2 h-7 w-64" />
              <Skeleton className="h-3 w-full max-w-md" />
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 border-b border-gray-100 px-5 py-4 sm:grid-cols-3 lg:grid-cols-7">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-3 w-14" />
              <Skeleton className="h-7 w-16" />
            </div>
          ))}
        </div>
        <Skeleton className="h-[420px] w-full rounded-none" />
        <div className="border-t border-gray-100 px-5 py-4">
          <div className="mb-3 flex gap-2">
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-8 w-20" />
          </div>
          <Skeleton className="h-40 w-full" />
        </div>
        <div className="border-t border-gray-100 px-5 py-4">
          <Skeleton className="mb-3 h-4 w-24" />
          <div className="flex gap-2">
            <Skeleton className="h-7 w-16 rounded-full" />
            <Skeleton className="h-7 w-16 rounded-full" />
          </div>
        </div>
        <div className="border-t border-gray-100 px-5 py-4 space-y-3">
          <Skeleton className="h-4 w-32" />
          {[0, 1].map((i) => (
            <div key={i} className="flex gap-3">
              <Skeleton className="h-8 w-8 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-28" />
                <Skeleton className="h-3 w-full max-w-sm" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function RouteDetailSkeleton() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6" aria-hidden="true">
      <div className="overflow-hidden rounded bg-white shadow-card">
        <div className="border-b border-gray-100 px-5 py-4">
          <div className="flex items-start gap-3">
            <Skeleton className="h-12 w-12 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-3 w-40" />
              <Skeleton className="mt-2 h-7 w-48" />
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 border-b border-gray-100 px-5 py-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-7 w-20" />
            </div>
          ))}
        </div>
        <Skeleton className="h-[420px] w-full rounded-none" />
        <div className="border-t border-gray-100 px-5 py-4 space-y-3">
          <Skeleton className="h-4 w-24" />
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-1">
              <div className="flex justify-between">
                <Skeleton className="h-3 w-28" />
                <Skeleton className="h-3 w-20" />
              </div>
              <Skeleton className="h-2 w-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function RouteTileSkeleton() {
  return (
    <div className="overflow-hidden rounded bg-white shadow-card" aria-hidden="true">
      <Skeleton className="h-40 w-full rounded-none" />
      <div className="space-y-2 p-4">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-28" />
      </div>
    </div>
  )
}

export function ProfileSkeleton() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6" aria-hidden="true">
      <div className="rounded bg-white p-6 shadow-card">
        <div className="flex items-start gap-4">
          <Skeleton className="h-20 w-20 rounded-full" />
          <div className="min-w-0 flex-1 space-y-3">
            <Skeleton className="h-6 w-40" />
            <div className="flex gap-4">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-28" />
            </div>
            <Skeleton className="h-9 w-28" />
          </div>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="space-y-1.5">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-5 w-20" />
            </div>
          ))}
        </div>
      </div>
      <div className="mt-6 space-y-4">
        <ActivityCardSkeleton />
        <ActivityCardSkeleton />
      </div>
    </div>
  )
}

export function FormCardSkeleton({ fields = 3, wide = false }) {
  return (
    <div
      className={`mx-auto px-4 py-10 ${wide ? 'max-w-4xl' : 'max-w-lg'}`}
      aria-hidden="true"
    >
      <Skeleton className="h-6 w-48" />
      {wide && <Skeleton className="mt-4 h-[360px] w-full" />}
      <div className="mt-6 space-y-4 rounded bg-white p-6 shadow-card">
        {Array.from({ length: fields }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-10 w-full" />
          </div>
        ))}
        <Skeleton className="h-10 w-28" />
      </div>
    </div>
  )
}

export function SettingsSkeleton() {
  return (
    <div className="mx-auto max-w-lg space-y-6 px-4 py-10" aria-hidden="true">
      <div className="space-y-2">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-4 w-64" />
      </div>
      {[0, 1, 2].map((i) => (
        <div key={i} className="space-y-4 rounded bg-white p-6 shadow-card">
          <Skeleton className="h-5 w-28" />
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
    </div>
  )
}

export function PeopleRowSkeleton({ withActions = false, withButton = false }) {
  return (
    <li className="flex items-center gap-3 rounded bg-white p-4 shadow-card" aria-hidden="true">
      <Skeleton className="h-10 w-10 rounded-full" />
      <div className="min-w-0 flex-1 space-y-2">
        <Skeleton className="h-4 w-36" />
        {withActions && <Skeleton className="h-3 w-24" />}
      </div>
      {withActions && (
        <>
          <Skeleton className="h-8 w-20" />
          <Skeleton className="h-8 w-20" />
        </>
      )}
      {withButton && !withActions && <Skeleton className="h-8 w-24" />}
    </li>
  )
}

export function LeaderRowSkeleton() {
  return (
    <div className="flex items-center gap-2" aria-hidden="true">
      <Skeleton className="h-3 w-4" />
      <Skeleton className="h-8 w-8 rounded-full" />
      <Skeleton className="h-4 flex-1" />
      <Skeleton className="h-4 w-12" />
    </div>
  )
}

export function AppShellSkeleton() {
  return (
    <div className="min-h-screen" aria-busy="true" aria-label="Загрузка">
      <header className="sticky top-0 z-[1100] border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <Skeleton className="h-7 w-28" />
            <div className="hidden gap-2 sm:flex">
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-8 w-20" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="h-8 w-8 rounded-full" />
            <Skeleton className="h-8 w-8 rounded-full" />
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="flex flex-col gap-6 lg:flex-row">
          <div className="min-w-0 flex-1 space-y-4 lg:max-w-2xl">
            <ActivityCardSkeleton />
            <ActivityCardSkeleton />
          </div>
          <div className="hidden w-72 shrink-0 lg:block">
            <div className="rounded bg-white p-4 shadow-card space-y-3">
              <Skeleton className="h-4 w-28" />
              <LeaderRowSkeleton />
              <LeaderRowSkeleton />
              <LeaderRowSkeleton />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function SurfaceCoverageSkeleton() {
  return (
    <div className="space-y-2" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div key={i} className="space-y-1">
          <div className="flex justify-between">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-3 w-20" />
          </div>
          <Skeleton className="h-2 w-full" />
        </div>
      ))}
    </div>
  )
}
