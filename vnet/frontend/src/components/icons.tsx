/** Hand-rolled stroke icons — no icon package, no extra bundle weight. */

import type { SVGProps } from "react";

type Props = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 18, children, ...rest }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const DashboardIcon = (p: Props) => (
  <Icon {...p}>
    <rect x="3" y="3" width="7" height="9" rx="1.5" />
    <rect x="14" y="3" width="7" height="5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" />
    <rect x="3" y="16" width="7" height="5" rx="1.5" />
  </Icon>
);

export const TopologyIcon = (p: Props) => (
  <Icon {...p}>
    <circle cx="12" cy="4.5" r="2.5" />
    <circle cx="5" cy="19" r="2.5" />
    <circle cx="19" cy="19" r="2.5" />
    <path d="M12 7v4M12 11H5v5.5M12 11h7v5.5" />
  </Icon>
);

export const DevicesIcon = (p: Props) => (
  <Icon {...p}>
    <rect x="2.5" y="6" width="19" height="5" rx="1.5" />
    <rect x="2.5" y="14" width="19" height="5" rx="1.5" />
    <path d="M6 8.5h.01M6 16.5h.01M9 8.5h.01M9 16.5h.01" />
  </Icon>
);

export const ClientsIcon = (p: Props) => (
  <Icon {...p}>
    <circle cx="9" cy="8" r="3.2" />
    <path d="M3.5 20a5.5 5.5 0 0 1 11 0" />
    <path d="M16 11.5a3 3 0 0 0 0-6" />
    <path d="M17.5 20a5.5 5.5 0 0 0-2.2-4.4" />
  </Icon>
);

export const TrafficIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M3 17.5 8 11l4 3.5L21 5" />
    <path d="M21 10V5h-5" />
    <path d="M3 21h18" />
  </Icon>
);

export const InsightsIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M12 3.5 21 19H3z" />
    <path d="M12 10v4M12 16.6h.01" />
  </Icon>
);

export const SettingsIcon = (p: Props) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2.5v2.2M12 19.3v2.2M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6" />
  </Icon>
);

export const GatewayIcon = (p: Props) => (
  <Icon {...p}>
    <rect x="2.5" y="9" width="19" height="9" rx="2" />
    <path d="M6 13h.01M9 13h.01M12 13h.01" />
    <path d="M7 6a7 7 0 0 1 10 0" />
  </Icon>
);

export const SwitchIcon = (p: Props) => (
  <Icon {...p}>
    <rect x="2.5" y="7" width="19" height="10" rx="2" />
    <path d="M6 11.5v2M9 11.5v2M12 11.5v2M15 11.5v2M18 11.5v2" />
  </Icon>
);

export const ApIcon = (p: Props) => (
  <Icon {...p}>
    <circle cx="12" cy="16.5" r="3" />
    <path d="M6.4 11.2a7.5 7.5 0 0 1 11.2 0" />
    <path d="M3.4 7.6a12 12 0 0 1 17.2 0" />
  </Icon>
);

export const CameraIcon = (p: Props) => (
  <Icon {...p}>
    <rect x="2.5" y="7" width="14" height="10" rx="2" />
    <path d="M16.5 11 21.5 8v8l-5-3z" />
  </Icon>
);

export const CloudIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M7 18h10a4 4 0 0 0 .4-8A6 6 0 0 0 6 10.5 3.8 3.8 0 0 0 7 18z" />
  </Icon>
);

export const PlusIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);

export const CloseIcon = (p: Props) => (
  <Icon {...p}>
    <path d="m6 6 12 12M18 6 6 18" />
  </Icon>
);

export const TrashIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" />
  </Icon>
);

export const ChevronIcon = (p: Props) => (
  <Icon {...p}>
    <path d="m9 6 6 6-6 6" />
  </Icon>
);

export const SearchIcon = (p: Props) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4.5 4.5" />
  </Icon>
);

export const BoltIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M13 2.5 4.5 13.5H11l-1 8 8.5-11H12z" />
  </Icon>
);

export const RefreshIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M20 11a8 8 0 1 0-1.6 5.6" />
    <path d="M20 20v-5h-5" />
  </Icon>
);

export const LINE_ICONS = {
  gateway: GatewayIcon,
  switch: SwitchIcon,
  ap: ApIcon,
  protect: CameraIcon,
  other: DevicesIcon,
} as const;
