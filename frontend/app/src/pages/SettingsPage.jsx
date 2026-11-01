import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { meApi } from '../api/endpoints'
import { useAuth } from '../hooks/AuthContext'
import Avatar from '../components/Avatar'
import { ButtonSpinner, SettingsSkeleton } from '../components/skeletons'

const zoneInputClass = 'w-20 rounded border border-gray-300 px-2 py-1 text-sm'

function ZonesEditor({ title, hint, zones, onChange, unit }) {
  return (
    <div className="rounded border border-gray-200 bg-feed px-4 py-4">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-0.5 text-xs text-ink-muted">{hint}</p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-ink-muted">
              <th className="py-1 pr-2 font-semibold">Зона</th>
              <th className="py-1 pr-2 font-semibold">От</th>
              <th className="py-1 font-semibold">До</th>
            </tr>
          </thead>
          <tbody>
            {(zones || []).map((zone, i) => (
              <tr key={i} className="border-t border-gray-200">
                <td className="py-2 pr-2">
                  <span className="font-medium text-ink">Z{i + 1}</span>{' '}
                  <span className="text-ink-muted">{zone.name}</span>
                </td>
                <td className="py-2 pr-2">
                  <input
                    type="number"
                    min={0}
                    className={zoneInputClass}
                    value={zone.min ?? ''}
                    onChange={(e) => {
                      const next = zones.map((z, idx) =>
                        idx === i ? { ...z, min: e.target.value === '' ? null : Number(e.target.value) } : z,
                      )
                      onChange(next)
                    }}
                  />
                </td>
                <td className="py-2">
                  {i === zones.length - 1 ? (
                    <span className="text-ink-muted">∞</span>
                  ) : (
                    <input
                      type="number"
                      min={0}
                      className={zoneInputClass}
                      value={zone.max ?? ''}
                      onChange={(e) => {
                        const next = zones.map((z, idx) =>
                          idx === i
                            ? { ...z, max: e.target.value === '' ? null : Number(e.target.value) }
                            : z,
                        )
                        onChange(next)
                      }}
                    />
                  )}
                  <span className="ml-1 text-xs text-ink-muted">{unit}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { refreshMe, logout } = useAuth()
  const navigate = useNavigate()
  const [me, setMe] = useState(null)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const [firstName, setFirstName] = useState('')
  const [email, setEmail] = useState('')
  const [telegram, setTelegram] = useState('')
  const [instagram, setInstagram] = useState('')
  const [vk, setVk] = useState('')
  const [ftp, setFtp] = useState('')
  const [maxHr, setMaxHr] = useState('')
  const [isPublic, setIsPublic] = useState(true)
  const [powerZones, setPowerZones] = useState([])
  const [hrZones, setHrZones] = useState([])
  const [photo, setPhoto] = useState(null)

  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [intervalsKey, setIntervalsKey] = useState('')
  const [garminKey, setGarminKey] = useState('')
  const [deletePassword, setDeletePassword] = useState('')

  useEffect(() => {
    meApi
      .get()
      .then((data) => {
        setMe(data)
        setFirstName(data.first_name || '')
        setEmail(data.email || '')
        setTelegram(data.telegram || '')
        setInstagram(data.instagram || '')
        setVk(data.vk || '')
        setFtp(data.ftp ?? '')
        setMaxHr(data.max_heart_rate ?? '')
        setIsPublic(!!data.is_public)
        setPowerZones(data.power_zones || [])
        setHrZones(data.hr_zones || [])
      })
      .catch((err) => setError(err.message))
  }, [])

  async function saveProfile(e, recalculate = false) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setMsg('')
    try {
      const body = {
        first_name: firstName,
        email,
        telegram,
        instagram,
        vk,
        is_public: isPublic,
        power_zones: powerZones,
        hr_zones: hrZones,
        recalculate_zones: recalculate,
      }
      if (ftp !== '') body.ftp = Number(ftp)
      if (maxHr !== '') body.max_heart_rate = Number(maxHr)

      let data
      if (photo) {
        const fd = new FormData()
        Object.entries(body).forEach(([k, v]) => {
          if (k === 'power_zones' || k === 'hr_zones') {
            fd.append(k, JSON.stringify(v))
          } else if (typeof v === 'boolean') {
            fd.append(k, v ? 'true' : 'false')
          } else if (v != null) {
            fd.append(k, String(v))
          }
        })
        fd.append('photo', photo)
        // Photo upload: send photo first via multipart, then JSON for zones
        data = await meApi.update(fd)
        data = await meApi.update({
          power_zones: powerZones,
          hr_zones: hrZones,
          recalculate_zones: recalculate,
        })
      } else {
        data = await meApi.update(body)
      }
      setMe(data)
      setPowerZones(data.power_zones || [])
      setHrZones(data.hr_zones || [])
      setPhoto(null)
      await refreshMe()
      setMsg('Профиль сохранён')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function changePassword(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setMsg('')
    try {
      await meApi.password({
        old_password: oldPassword,
        new_password1: newPassword,
        new_password2: newPassword,
      })
      setOldPassword('')
      setNewPassword('')
      setMsg('Пароль изменён')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function connectIntervals(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await meApi.intervalsConnect({ api_key: intervalsKey })
      setIntervalsKey('')
      const data = await meApi.get()
      setMe(data)
      setMsg('Intervals.icu подключён')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function connectGarmin(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await meApi.garminConnect({ api_key: garminKey })
      setGarminKey('')
      const data = await meApi.get()
      setMe(data)
      setMsg('Garmin подключён')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function deleteAccount(e) {
    e.preventDefault()
    if (!window.confirm('Удалить аккаунт безвозвратно?')) return
    setBusy(true)
    try {
      await meApi.deleteAccount({ password: deletePassword })
      await logout()
      navigate('/login/')
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  if (!me) return <SettingsSkeleton />

  return (
    <div className="mx-auto max-w-lg space-y-6 px-4 py-10">
      <div>
        <h1 className="text-xl font-bold text-ink">Настройки</h1>
        <p className="mt-1 text-sm text-ink-muted">Профиль, приватность и безопасность аккаунта.</p>
      </div>
      {msg && (
        <div className="rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">{msg}</div>
      )}
      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      <section className="rounded bg-white p-6 shadow-card">
        <h2 className="text-base font-bold text-ink">Профиль</h2>
        <form
          className="mt-5 space-y-5"
          onSubmit={(e) => saveProfile(e, false)}
          encType="multipart/form-data"
        >
          <div className="flex items-center gap-4">
            <Avatar person={me} className="h-20 w-20 text-xl" />
            <div>
              <label className="btn-ghost cursor-pointer text-xs sm:text-sm">
                Сменить аватар
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => setPhoto(e.target.files?.[0] || null)}
                />
              </label>
              {photo && <p className="mt-1 text-xs text-ink-muted">{photo.name}</p>}
            </div>
          </div>
          {[
            ['Отображаемое имя', firstName, setFirstName, 'text'],
            ['Почта', email, setEmail, 'email'],
            ['Telegram', telegram, setTelegram, 'text'],
            ['Instagram', instagram, setInstagram, 'text'],
            ['VK', vk, setVk, 'text'],
          ].map(([label, value, setter, type]) => (
            <div key={label}>
              <label className="field-label">{label}</label>
              <input
                type={type}
                className="field-input"
                value={value}
                onChange={(e) => setter(e.target.value)}
              />
            </div>
          ))}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="field-label">FTP (Вт)</label>
              <input
                type="number"
                className="field-input"
                value={ftp}
                onChange={(e) => setFtp(e.target.value)}
              />
            </div>
            <div>
              <label className="field-label">Макс. пульс</label>
              <input
                type="number"
                className="field-input"
                value={maxHr}
                onChange={(e) => setMaxHr(e.target.value)}
              />
            </div>
          </div>

          <ZonesEditor
            title="Зоны мощности"
            hint="7 зон Joe Friel от FTP."
            zones={powerZones}
            onChange={setPowerZones}
            unit="Вт"
          />
          <button
            type="button"
            className="btn-ghost text-xs"
            disabled={busy}
            onClick={(e) => saveProfile(e, true)}
          >
            {busy && <ButtonSpinner className="h-3 w-3" />}
            Пересчитать зоны
          </button>
          <ZonesEditor
            title="Зоны пульса"
            hint="7 зон Joe Friel от LTHR."
            zones={hrZones}
            onChange={setHrZones}
            unit="уд/мин"
          />

          <label className="flex cursor-pointer items-start gap-3 rounded border border-gray-200 bg-feed px-4 py-3">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
              className="mt-1"
            />
            <span>
              <span className="block text-sm font-semibold text-ink">Открытый профиль</span>
              <span className="mt-0.5 block text-xs text-ink-muted">
                Открытый — тренировки видят все. Закрытый — только подписчики.
              </span>
            </span>
          </label>
          <button type="submit" className="btn-brand w-full" disabled={busy}>
            {busy && <ButtonSpinner />}
            {busy ? 'Сохранение…' : 'Сохранить'}
          </button>
        </form>
      </section>

      <section className="rounded bg-white p-6 shadow-card">
        <h2 className="text-base font-bold text-ink">Пароль</h2>
        <form onSubmit={changePassword} className="mt-5 space-y-4">
          <div>
            <label className="field-label">Текущий пароль</label>
            <input
              type="password"
              className="field-input"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="field-label">Новый пароль</label>
            <input
              type="password"
              className="field-input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn-brand w-full" disabled={busy}>
            {busy && <ButtonSpinner />}
            {busy ? 'Сохранение…' : 'Сменить пароль'}
          </button>
        </form>
      </section>

      <section className="rounded bg-white p-6 shadow-card">
        <h2 className="text-base font-bold text-ink">Внешние сервисы</h2>
        <div className="mt-5 space-y-4">
          <div className="rounded border border-gray-200 bg-feed px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">Intervals.icu</p>
                <p className="text-xs text-ink-muted">
                  {me.intervals_connected ? 'Подключено' : 'Не подключено'}
                </p>
              </div>
              {me.intervals_connected && (
                <button
                  type="button"
                  className="btn-ghost text-xs"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    try {
                      await meApi.intervalsDisconnect()
                      setMe(await meApi.get())
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  {busy && <ButtonSpinner className="h-3 w-3" />}
                  Отключить
                </button>
              )}
            </div>
            {!me.intervals_connected && (
              <form onSubmit={connectIntervals} className="mt-3 space-y-2">
                <input
                  className="field-input"
                  placeholder="API key"
                  value={intervalsKey}
                  onChange={(e) => setIntervalsKey(e.target.value)}
                  required
                />
                <button type="submit" className="btn-brand" disabled={busy}>
                  {busy && <ButtonSpinner />}
                  {busy ? 'Подключение…' : 'Подключить'}
                </button>
              </form>
            )}
          </div>

          <div className="rounded border border-gray-200 bg-feed px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">Garmin</p>
                <p className="text-xs text-ink-muted">
                  {me.garmin_connected ? 'Подключено' : 'Не подключено'}
                </p>
              </div>
              {me.garmin_connected && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn-ghost text-xs"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true)
                      try {
                        await meApi.garminSyncZones()
                        setMe(await meApi.get())
                        setMsg('Зоны мощности синхронизированы')
                      } finally {
                        setBusy(false)
                      }
                    }}
                  >
                    {busy && <ButtonSpinner className="h-3 w-3" />}
                    Sync zones
                  </button>
                  <button
                    type="button"
                    className="btn-ghost text-xs"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true)
                      try {
                        await meApi.garminDisconnect()
                        setMe(await meApi.get())
                      } finally {
                        setBusy(false)
                      }
                    }}
                  >
                    {busy && <ButtonSpinner className="h-3 w-3" />}
                    Отключить
                  </button>
                </div>
              )}
            </div>
            {!me.garmin_connected && (
              <form onSubmit={connectGarmin} className="mt-3 space-y-2">
                <input
                  className="field-input"
                  placeholder="API key / token"
                  value={garminKey}
                  onChange={(e) => setGarminKey(e.target.value)}
                  required
                />
                <button type="submit" className="btn-brand" disabled={busy}>
                  {busy && <ButtonSpinner />}
                  {busy ? 'Подключение…' : 'Подключить'}
                </button>
              </form>
            )}
          </div>
        </div>
      </section>

      <section className="rounded bg-white p-6 shadow-card">
        <h2 className="text-base font-bold text-red-700">Удалить аккаунт</h2>
        <form onSubmit={deleteAccount} className="mt-5 space-y-4">
          <input
            type="password"
            className="field-input"
            placeholder="Пароль для подтверждения"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
            required
          />
          <button type="submit" className="btn-ghost w-full text-red-600" disabled={busy}>
            {busy && <ButtonSpinner />}
            {busy ? 'Удаление…' : 'Удалить аккаунт'}
          </button>
        </form>
      </section>
    </div>
  )
}
