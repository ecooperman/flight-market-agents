// The sidebar (Global.buildNav, shared-assets/theme.js). One page, so one entry plus Refresh.
Global.buildNav([
  { href: "/", icon: "compass", label: "Flights", active: true },
  { icon: "refresh", label: "Refresh", onclick: () => location.reload() },
]);
