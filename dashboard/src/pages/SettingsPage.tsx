import { useState, useEffect } from 'react';
import { getSettings, updateSetting, type Setting } from '../lib/api';
import { Save, Clock } from 'lucide-react';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

interface WorkingHours {
  [day: string]: { enabled: boolean; start: string; end: string };
}

const defaultHours: WorkingHours = Object.fromEntries(
  DAYS.map((d) => [d, { enabled: d !== 'Sunday', start: '09:00', end: '18:00' }])
);

export default function SettingsPage() {
  const [hours, setHours] = useState<WorkingHours>(defaultHours);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getSettings()
      .then((settings: Setting[]) => {
        const wh = settings.find((s) => s.key === 'working_hours');
        if (wh?.value) setHours(wh.value as unknown as WorkingHours);
      })
      .catch(console.error);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSetting('working_hours', hours as unknown as Record<string, unknown>);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const toggleDay = (day: string) => {
    setHours((prev) => ({
      ...prev,
      [day]: { ...prev[day], enabled: !prev[day].enabled },
    }));
  };

  const updateTime = (day: string, field: 'start' | 'end', value: string) => {
    setHours((prev) => ({
      ...prev,
      [day]: { ...prev[day], [field]: value },
    }));
  };

  return (
    <div className="animate-fade-in">
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 24 }}>
        <span className="gradient-text">Settings</span>
      </h1>

      <div className="glass-card" style={{ padding: 24, maxWidth: 700 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
          <Clock size={18} style={{ color: 'var(--color-accent)' }} />
          <h2 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Working Hours</h2>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginBottom: 24 }}>
          Configure when human agents are available for escalation. Outside these hours, users will receive an automated response.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {DAYS.map((day) => (
            <div
              key={day}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                padding: '10px 12px',
                borderRadius: 10,
                background: hours[day].enabled ? 'rgba(99, 102, 241, 0.05)' : 'transparent',
                border: `1px solid ${hours[day].enabled ? 'rgba(99, 102, 241, 0.15)' : 'var(--color-border)'}`,
                transition: 'all 0.2s ease',
              }}
            >
              <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', width: 140 }}>
                <input
                  type="checkbox"
                  checked={hours[day].enabled}
                  onChange={() => toggleDay(day)}
                  style={{ accentColor: '#65bc47', width: 16, height: 16 }}
                />
                <span style={{ fontSize: '0.9rem', fontWeight: 500, color: hours[day].enabled ? 'var(--color-text-primary)' : 'var(--color-text-muted)' }}>
                  {day}
                </span>
              </label>

              {hours[day].enabled && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input
                    type="time"
                    className="input"
                    value={hours[day].start}
                    onChange={(e) => updateTime(day, 'start', e.target.value)}
                    style={{ width: 120, padding: '6px 10px' }}
                  />
                  <span style={{ color: 'var(--color-text-muted)' }}>to</span>
                  <input
                    type="time"
                    className="input"
                    value={hours[day].end}
                    onChange={(e) => updateTime(day, 'end', e.target.value)}
                    style={{ width: 120, padding: '6px 10px' }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            <Save size={14} />
            {saving ? 'Saving...' : saved ? 'Saved ✓' : 'Save Working Hours'}
          </button>
        </div>
      </div>
    </div>
  );
}
