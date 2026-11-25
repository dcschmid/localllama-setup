const paths = {
  mark: '<path d="M4 20h16M7 15.5l1.2-4L16.5 3l4 4-8.4 8.4L7 17zM14.5 5l4 4"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  library: '<path d="M5 5v14M9 5v14M13 5v14M17 6l3 13"/>',
  search: '<circle cx="10.5" cy="10.5" r="5.5"/><path d="m15 15 4.5 4.5"/>',
  settings: '<path d="M5 6h14M5 12h14M5 18h14M9 4v4m6 2v4m-5 2v4"/>',
  chat: '<path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 3z"/>',
  book: '<path d="M12 6c-3-2-6-2.5-9-1v13c3-1.5 6-1 9 1m0-13c3-2 6-2.5 9-1v13c-3-1.5-6-1-9 1m0-13v13"/>',
  research: '<circle cx="10.5" cy="10.5" r="6"/><path d="M10.5 7v7M7 10.5h7m1 4.5 5 5"/>',
  picture: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.15"/><path d="m4 17 5-4 3 2 4-5 5 5"/>',
  game: '<path d="M7.5 7h9a3.4 3.4 0 0 1 3.4 2.8l1 4.7a2.5 2.5 0 0 1-4.15 2.35L14.6 15H9.4l-2.15 1.85A2.5 2.5 0 0 1 3.1 14.5l1-4.7A3.4 3.4 0 0 1 7.5 7zM8 9.5v3M6.5 11h3m6.5-1h.01m2 2h.01"/>',
  arrow: '<path d="M4 12h15m-5-5 5 5-5 5"/>',
  turn: '<path d="M5 6v8h14m-4-4 4 4-4 4"/>',
  up: '<path d="M12 19V5m-6 6 6-6 6 6"/>',
  moon: '<path d="M20.5 14.1a8.4 8.4 0 0 1-10.6-10.6A8.5 8.5 0 1 0 20.5 14z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  text: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8h8m-8 4h8m-8 4h5"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v11h14V9m-9 4h4"/>',
  trash: '<path d="M4 7h16m-2 0-1 13H7L6 7m3 0V4h6v3m-5 4v5m4-5v5"/>',
  paperclip: '<path d="m8 13 6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l8-8m-4 11 8-8"/>',
};

export type IconName = keyof typeof paths;

export function icon(name: IconName) {
  return '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + paths[name] + '</svg>';
}
