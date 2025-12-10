const favicon = document.getElementById('favicon');
const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
favicon.href = isDark ? '/hermes/assets/favicon_dark.png' : '/hermes/assets/favicon_light.png';
