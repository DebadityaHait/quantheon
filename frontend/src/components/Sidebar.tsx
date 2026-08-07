import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import type { Route } from '../types';
import './Sidebar.css';

export type SidebarItem = {
  route: Route;
  label: string;
};

const navigationGroups: { label: string; routes: Route[] }[] = [
  { label: 'Desk', routes: ['chat', 'rfq', 'try-solve', 'client'] },
  { label: 'Trading', routes: ['positions', 'booking', 'confirmations', 'settlement', 'portfolios', 'instruments'] },
  { label: 'Risk & hedging', routes: ['risk', 'hedging', 'limits', 'greeks-landscape', 'scenario-test', 'backtest'] },
  { label: 'Operations', routes: ['tasks', 'reports', 'workflows', 'skills', 'memory', 'audit', 'tracing', 'arena'] },
  { label: 'Configuration', routes: ['pricing-parameters', 'engine-configs', 'model-maintenance'] },
];

type Props = {
  items: SidebarItem[];
  active: Route;
  onNavigate: (route: Route) => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
};

export function Sidebar({
  items,
  active,
  onNavigate,
  collapsed = false,
  onToggleCollapsed,
}: Props) {
  return (
    <aside className={`wl-sidebar${collapsed ? ' wl-sidebar--collapsed' : ''}`} aria-label="Primary navigation">
      <div className="wl-sidebar__brand">
        <button
          type="button"
          className="wl-sidebar__brand-toggle"
          onClick={onToggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-pressed={collapsed}
        >
          <span className="wl-sidebar__brand-mark" aria-hidden="true">Q</span>
          {!collapsed && (
            <span className="wl-sidebar__brand-text" aria-hidden="true">
              <strong>Quantheon</strong>
              <span>Derivatives desk</span>
            </span>
          )}
          <span className="wl-sidebar__toggle-icon" aria-hidden="true">
            {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </span>
        </button>
      </div>
      {!collapsed && (
        <nav className="wl-sidebar__nav">
          {[
            ...navigationGroups.map((group) => ({
              label: group.label,
              items: items.filter((item) => group.routes.includes(item.route)),
            })),
            { label: 'Other', items: items.filter((item) => !navigationGroups.some((group) => group.routes.includes(item.route))) },
          ].filter((group) => group.items.length > 0).map((group) => (
            <div className="wl-sidebar__nav-group" key={group.label}>
              <div className="wl-sidebar__nav-label">{group.label}</div>
              {group.items.map((item) => (
                <button
                  key={item.route}
                  type="button"
                  className={`wl-sidebar__nav-item ${item.route === active ? 'wl-sidebar__nav-item--active' : ''}`.trim()}
                  aria-current={item.route === active ? 'page' : undefined}
                  onClick={() => onNavigate(item.route)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </nav>
      )}
    </aside>
  );
}
