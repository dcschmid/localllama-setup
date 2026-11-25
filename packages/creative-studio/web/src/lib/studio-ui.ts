import { micromark } from 'micromark';
import { ApiError, esc } from './core';
import { icon, type IconName } from './icons';

export const main = document.querySelector<HTMLElement>('#main')!;
export const details = document.querySelector<HTMLDialogElement>('#details')!;
export const $ = <T extends HTMLElement = HTMLElement>(selector: string, root: ParentNode = document) =>
  root.querySelector<T>(selector);

export function mark() {
  return '<span class="brand-mark" aria-hidden="true">' + icon('mark') + '</span>';
}

export function button(action: string, label: string, glyph?: IconName, style = 'button quiet', value?: string) {
  return `<button class="${style}" type="button" data-action="${action}"${value ? ` data-value="${esc(value)}"` : ''}>${glyph ? icon(glyph) : ''}${esc(label)}</button>`;
}

export function iconButton(action: string, label: string, glyph: IconName, value?: string) {
  return `<button class="icon-button" type="button" aria-label="${esc(label)}" title="${esc(label)}" data-action="${action}"${value ? ` data-value="${esc(value)}"` : ''}>${icon(glyph)}</button>`;
}

export function announce(text: string) {
  $('#announcement')!.textContent = text;
}

export function showDialog(title: string, body: string, wide = false) {
  details.classList.toggle('wide-dialog', wide);
  details.innerHTML = `<div class="dialog-content"><div class="dialog-top"><h2 id="details-title">${esc(title)}</h2>
    <form method="dialog"><button class="icon-button" aria-label="Dialog schließen">${icon('x')}</button></form>
    </div>${body}</div>`;
  if (!details.open) details.showModal();
  else $('button', details)?.focus();
}

export function dialogForm(title: string, fields: string, submit: string, onSubmit: (data: FormData) => Promise<void>) {
  showDialog(title, `<form id="dialog-form">${fields}<p id="dialog-status" role="status"></p>
    <button class="button primary" type="submit">${esc(submit)}</button></form>`);
  const form = $<HTMLFormElement>('#dialog-form', details)!;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const values = new FormData(form);
    const submitter = event.submitter as HTMLButtonElement;
    submitter.disabled = true;
    try {
      await onSubmit(values);
      if (form.isConnected && details.open) details.close();
    } catch (error) {
      $('#dialog-status', form)!.textContent = describe(error);
    } finally {
      submitter.disabled = false;
    }
  });
}

export const visualErrors: Record<string, string> = {
  visual_model_unavailable: 'Das gewählte Bildmodell ist lokal nicht installiert.',
  visual_format_unavailable: 'Das Bildmodell unterstützt das gewählte Seitenverhältnis in dieser Konfiguration nicht.',
  visual_recipe_unavailable: 'Das Guided Preset ist für dieses Modell im lokalen Katalog nicht verfügbar.',
  visual_profile_changed: 'Das Bildprofil wurde geändert. Öffne es erneut.',
  visual_profile_invalid: 'Prüfe Profilname, Einstellungen und Kapitelbereich.',
  visual_story_required: 'Wähle die Geschichte aus, zu der das Bild gehört.',
  visual_chapter_unwritten: 'Das Kapitel braucht einen gespeicherten Text für diese Illustration.',
  visual_reference_invalid: 'Die Bildreferenz ist ungültig oder gehört zu einer anderen Geschichte.',
  visual_reference_unavailable: 'Das Modell unterstützt für diese Installation keine verifizierte Bildvorlage.',
  visual_compose_invalid: 'Der lokale Bilddienst hat die Kombination aus Motiv und Einstellungen abgelehnt.',
};

export const productionErrors: Record<string, string> = {
  ...visualErrors,
  production_approval_required: 'Gib zuerst die Story-Planung frei.',
  production_plan_changed: 'Die Planung oder ein Kapitel wurde geändert. Öffne die aktuelle Planversion.',
  production_plan_checkpoint_conflict: 'Dieser Entwurf betrifft bereits begonnene Kapitel oder die Grundplanung. Die Produktion bleibt pausiert und beim bisherigen Plan.',
  production_plan_invalid: 'Prüfe die Planung, Wortzahlen und Kapitelüberschriften.',
  production_existing_chapters: 'Dieser Chat enthält Kapitel aus einem anderen Schreibauftrag. Beginne die Produktion in einem eigenen Story-Chat.',
  production_manages_chapters: 'Der Produktionsauftrag verwaltet die Kapitel. Du kannst den vorhandenen Text im Editor bearbeiten.',
  production_fix_required: 'Bearbeite zuerst den Konflikt im Kapitel und speichere die Änderung.',
  production_impact_required: 'Prüfe und bestätige die Auswirkungen der Planänderung.',
  production_art_review_required: 'Bestätige die Bildserie nach der Sichtprüfung.',
  production_manuscript_partial: 'Der vollständige Export ist verfügbar, sobald Texte, Bilder und Dateien geprüft sind.',
  production_manuscript_missing: 'Zu diesem Chat ist kein Manuskript in der Story-Produktion gespeichert.',
  production_export_missing: 'Mindestens eine geprüfte Exportdatei fehlt oder wurde verändert.',
  production_export_invalid: 'Der Export stimmt nicht mit den gespeicherten Kapiteln und Bildern überein.',
  production_mdx_invalid: 'Der lokale MDX-Compiler konnte das Manuskript nicht lesen.',
  production_mdx_tool_unavailable: 'Der lokale MDX-Compiler ist nicht verfügbar.',
  production_audit_evidence: 'Für mindestens ein Kapitel fehlt der technische Nachweis der Textprüfung.',
  production_placeholder: 'Der Kapiteltext enthält einen Platzhalter aus einer Modellantwort.',
  production_role_unavailable: 'Das konfigurierte lokale Modellprofil ist derzeit nicht verfügbar.',
  production_context_budget: 'Dieses Modellprofil hat für den nächsten Abschnitt zu wenig Kontext.',
  production_image_evidence: 'Die ausgewählte Szene ließ sich im gespeicherten Kapitel nicht belegen.',
  production_image_failed: 'Der Bilddienst hat den Bildauftrag abgebrochen oder als fehlgeschlagen gemeldet.',
  production_image_wait_timeout: 'Der Bilddienst hat den bestehenden Auftrag innerhalb der Wartezeit nicht abgeschlossen.',
  production_image_uncertain: 'Der Bilddienst konnte den Auftrag nicht eindeutig bestätigen.',
  image_archive_missing: 'Die fertige Datei ist im Bildarchiv derzeit nicht verfügbar.',
  image_invalid_png: 'Der Bilddienst hat keine gültige PNG-Datei geliefert.',
  image_dimensions_mismatch: 'Die Bilddatei hat ein anderes Format als angefordert.',
  image_job_not_found: 'Der gespeicherte Bildauftrag war beim Abruf nicht verfügbar.',
  gpu_wait_timeout: 'Für den Bildauftrag wurde innerhalb der Wartezeit kein GPU-Slot frei.',
  image_service_unreachable: 'Der lokale Bilddienst ist nicht erreichbar.',
  backend_not_ready: 'Der lokale Bilddienst ist noch nicht bereit.',
  production_upstream_http: 'Der lokale Modell- oder Bilddienst hat den Aufruf mit einem HTTP-Fehler beendet.',
  production_upstream_unavailable: 'Der lokale Modell- oder Bilddienst war vorübergehend nicht erreichbar.',
  production_checkpoint_write: 'Der Arbeitsschritt konnte nicht in der lokalen Datenbank gespeichert werden.',
  story_model_format: 'Das lokale Modell hat kein verwendbares strukturiertes Ergebnis geliefert.',
  story_output_truncated: 'Die Modellantwort endete vor Abschluss des Ergebnisses.',
  production_manuscript_blocked: 'Die Manuskriptprüfung hat einen Konflikt gefunden.',
  story_length_failed: 'Eine Szene hat die verlangte Länge, Sprache oder Textqualität nicht erreicht.',
  production_step_failed: 'Der Schritt konnte nicht abgeschlossen werden. Du kannst ihn erneut ausführen.',
};

export const storyErrors: Record<string, string> = {
  story_input_invalid: 'Prüfe die ausgefüllten Felder und die gewählte Eröffnung.',
  story_words_invalid: 'Die Mindestwortzahl darf die Höchstwortzahl nicht überschreiten.',
  story_job_running: 'Für diese Geschichte läuft bereits ein Schreibauftrag.',
  story_chapter_missing: 'Dieses Kapitel ist nicht verfügbar.',
  story_chapter_unwritten: 'Für diese Anfrage gibt es noch keinen Kapiteltext im Chat. Lass das Kapitel zuerst schreiben.',
  chat_context_invalid: 'Dieser Inhalt gehört zu einem anderen Chat.',
  story_has_draft: 'Dieses Kapitel enthält bereits einen Entwurf. Öffne es zum Überarbeiten im Editor.',
  story_approved: 'Hebe die Freigabe vor dem Bearbeiten auf.',
  story_status_invalid: 'Speichere zuerst einen Kapiteltext.',
  story_no_text: 'Schreibe zuerst mindestens ein Kapitel.',
  story_context_changed: 'Ein beteiligtes Dokument wurde während des Auftrags geändert. Starte den Auftrag erneut.',
  story_length_failed: 'Das Modell hat den Zielbereich oder die gewünschte Sprache nicht zuverlässig erreicht.',
  story_repetition_failed: 'Das Modell hat wiederholt bereits vorhandenen Text übernommen. Der bisherige Entwurf bleibt erhalten.',
  story_metatext: 'Das Modell hat Schreibanweisungen in den Erzähltext übernommen. Der bisherige Entwurf bleibt erhalten.',
  story_opening_too_long: 'Der Zielbereich ist kürzer als die vorhandene Eröffnung.',
  story_model_format: 'Das Modell hat keine vollständige strukturierte Antwort geliefert.',
  story_outline_incomplete: 'Die Modellantwort enthielt weniger Kapitelpläne als bestellt.',
  story_chat_mismatch: 'Öffne den Chat, zu dem die Geschichte gehört.',
  story_save_first: 'Speichere zuerst die offenen Änderungen.',
  story_job_closed: 'Der Auftrag ist bereits beendet.',
};

const errors: Record<string, string> = {
  ...storyErrors,
  ...productionErrors,
  creative_choice_required: 'Die Nachricht nennt Alternativen. Formuliere den gewünschten Auftrag oder verbinde beide Aufgaben mit „und“.',
  creative_language_ambiguous: 'Bitte gib an, in welcher Sprache ich den Text schreiben soll.',
  word_range_unsupported: 'Gib eine Wortzahl oder Spanne zwischen 1 und 2600 Wörtern an.',
  image_format_unsupported: 'Dieses Seitenverhältnis ist für den Bildauftrag nicht verfügbar.',
  image_options_invalid: 'Eine der Bildoptionen ist ungültig. Prüfe Modell, Auflösung, Stil oder Seed.',
  image_prompt_required: 'Was soll auf dem Bild zu sehen sein?',
  writing_service_unavailable: 'Das Schreibmodell oder der Human Writing Skill ist gerade nicht erreichbar.',
  editorial_choices_invalid: 'Diese Absätze lassen sich nicht gemeinsam übernehmen. Ändere die Auswahl oder übernimm den gesamten Vorschlag.',
  router_unreachable: 'Das Schreib- oder Chatmodell ist gerade nicht erreichbar.',
  stream_incomplete: 'Die Antwort wurde unterbrochen. Du kannst deine Nachricht erneut senden.',
  stream_unavailable: 'Die Antwort konnte gerade nicht erzeugt werden.',
  image_service_unreachable: 'Der Bilddienst ist gerade nicht erreichbar.',
  image_export_failed: 'Ein eingebettetes Bild konnte für den Export nicht geladen werden.',
  document_changed: 'Das Dokument wurde in einem anderen Fenster geändert. Dein Entwurf bleibt hier erhalten.',
  project_name_invalid: 'Gib einen Namen mit höchstens 180 Zeichen ein.',
  research_inactive: 'Die Recherche ist bereits beendet.',
  gpu_wait_timeout: 'Der Bilddienst wurde während der Wartezeit nicht frei.',
  lint_failed: 'Die Schreibstilprüfung ist gerade nicht erreichbar.',
  editorial_text_limit: 'Wähle einen kürzeren Abschnitt für die Modellprüfung oder Überarbeitung.',
  editorial_request_invalid: 'Wähle einen Text und gib bei einem eigenen Auftrag eine Anweisung ein.',
  editorial_range_invalid: 'Die Auswahl konnte nicht gelesen werden. Markiere die Textstelle erneut.',
  editorial_fidelity_failed: 'Der Vorschlag hat die Vorgaben zu Sprache, Länge oder Texttreue verfehlt. Probiere einen engeren Auftrag.',
  editorial_protected_selection: 'Die Auswahl schneidet einen Link, Codeblock oder anderen geschützten Markdown-Bereich. Markiere den gesamten Bereich oder lass ihn aus.',
  editorial_output_truncated: 'Die Modellantwort war unvollständig. Verwende eine kürzere Passage.',
  editorial_run_closed: 'Dieser Vorschlag wurde bereits abgeschlossen.',
  editorial_no_changes: 'Der Vorschlag enthält keine Änderungen.',
  writing_template_mismatch: 'Das Schreibprofil konnte die erforderlichen Human-Writing-Regeln nicht nachweisen.',
  question_required: 'Für die Recherche fehlt noch eine konkrete Frage.',
  image_job_not_found: 'Dieser Bildauftrag ist nicht mehr verfügbar.',
  image_not_found: 'Dieses Bild ist nicht mehr verfügbar.',
  organizer_not_found: 'Dieser Eintrag ist nicht verfügbar. Aktualisiere die Ansicht.',
  organizer_name_invalid: 'Gib einen Namen mit höchstens 180 Zeichen ein.',
  organizer_name_conflict: 'An diesem Ort gibt es bereits einen Ordner mit diesem Namen.',
  organizer_folder_cycle: 'Ein Ordner kann nicht in sich selbst oder einen seiner Unterordner verschoben werden.',
  organizer_folder_depth: 'Wähle einen Ordner weiter oben. Die maximale Verschachtelung ist erreicht.',
  organizer_selection_changed: 'Die Auswahl hat sich geändert. Öffne die Aktion erneut, um die aktuellen Einträge zu prüfen.',
  organizer_work_running: 'Für diese Inhalte läuft noch ein Auftrag. Warte auf das Ergebnis oder brich den Auftrag im Chat ab.',
  organizer_image_in_use: 'Das Bild wird noch verwendet. Entferne zuerst die Verknüpfungen oder stelle das Bild wieder her.',
  attachment_too_large: 'Anhänge dürfen höchstens 10 MB groß sein.',
};

export function describe(error: unknown, fallback = 'Die Aktion ist fehlgeschlagen. Bitte versuche es erneut.') {
  return error instanceof ApiError ? errors[error.code] ?? visualErrors[error.code.split(':')[0]] ?? fallback : fallback;
}

export function safeImageId(value: unknown): value is string {
  return typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
}

export function imageUrl(id: string) { return '/api/images/files/' + encodeURIComponent(id); }

export function markdown(value: string, verifiedAttachments = true) {
  const template = document.createElement('template');
  template.innerHTML = micromark(value);
  for (const heading of template.content.querySelectorAll('h1,h2,h3,h4,h5,h6')) {
    const level = Math.min(Number(heading.tagName[1]) + 2, 6);
    const adjusted = document.createElement('h' + level);
    adjusted.append(...heading.childNodes);
    heading.replaceWith(adjusted);
  }
  for (const img of template.content.querySelectorAll('img')) {
    if (!verifiedAttachments || !/^\/api\/images\/files\/[a-f0-9]{32}$/.test(img.getAttribute('src') ?? '')) {
      img.replaceWith(document.createTextNode(img.alt));
    } else img.loading = 'lazy';
  }
  for (const link of template.content.querySelectorAll('a')) {
    const url = link.getAttribute('href') ?? '';
    if (!verifiedAttachments && (/\b(?:download|herunterlad\w*|export(?:datei)?)\b/iu.test(link.textContent ?? '')
      || /\.(?:mdx?|zip|png)(?:[?#]|$)/iu.test(url))) {
      link.removeAttribute('href');
    } else if (/^https?:\/\//i.test(url)) {
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    } else if (!url.startsWith('#') || url.startsWith('#/')) {
      link.removeAttribute('href');
    }
  }
  return template.innerHTML;
}

export function sourceLink(url: string, text: string) {
  return /^https?:\/\//i.test(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text || url)}</a>` : esc(text || url);
}

export function download(name: string, content: BlobPart, type = 'text/markdown') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function formatDate(epoch?: number) {
  if (!epoch) return '';
  return new Intl.DateTimeFormat('de', { dateStyle: 'medium' }).format(epoch * 1000);
}
