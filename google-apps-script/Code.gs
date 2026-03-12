/**
 * PM Newsletter — Google Apps Script
 *
 * This script runs inside Google Workspace and handles:
 * 1. Collecting Google Drive activity (files modified, comments, shares)
 * 2. Creating formatted Google Docs with the newsletter content
 *
 * Deploy as a Web App to allow the Python script to call it.
 * Set a weekly trigger to auto-run.
 */

// ========== CONFIGURATION ==========
const CONFIG = {
  LOOKBACK_DAYS: 7,
  OUTPUT_FOLDER_NAME: "PM Newsletters",
  USER_EMAIL: "hehamilton@ebay.com",
};

// ========== WEB APP ENDPOINTS ==========

function doGet(e) {
  const action = (e && e.parameter && e.parameter.action) || "activity";
  let result;
  switch (action) {
    case "activity":
      result = getDriveActivity();
      break;
    case "health":
      result = { status: "ok", timestamp: new Date().toISOString() };
      break;
    default:
      result = { error: "Unknown action: " + action };
  }
  return ContentService
    .createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    const content = payload.content || "";
    const title = payload.title || "PM Newsletter — " + new Date().toLocaleDateString();
    const docUrl = createNewsletterDoc(title, content);
    return ContentService
      .createTextOutput(JSON.stringify({ success: true, url: docUrl }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// ========== DRIVE ACTIVITY ==========

function getDriveActivity() {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - CONFIG.LOOKBACK_DAYS);

  const modifiedFiles = getModifiedFiles(cutoffDate);
  const sharedWithMe = getRecentlyShared(cutoffDate);

  return {
    modified_files: modifiedFiles,
    shared_with_me: sharedWithMe,
    collected_at: new Date().toISOString(),
    lookback_days: CONFIG.LOOKBACK_DAYS,
  };
}

/**
 * Get files modified in the lookback period using DriveApp search.
 */
function getModifiedFiles(cutoffDate) {
  // DriveApp.searchFiles uses a simpler date format: 'yyyy-MM-dd'
  const dateStr = Utilities.formatDate(cutoffDate, Session.getScriptTimeZone(), "yyyy-MM-dd");
  const query = "modifiedDate > '" + dateStr + "' and trashed = false and mimeType != 'application/vnd.google-apps.folder'";

  const files = [];
  try {
    const iter = DriveApp.searchFiles(query);
    let count = 0;
    while (iter.hasNext() && count < 100) {
      const file = iter.next();
      files.push({
        id: file.getId(),
        name: file.getName(),
        type: mimeToType(file.getMimeType()),
        mime_type: file.getMimeType(),
        modified_time: file.getLastUpdated().toISOString(),
        last_modified_by: getLastEditor(file),
        is_owner: file.getOwner() && file.getOwner().getEmail() === CONFIG.USER_EMAIL,
        link: file.getUrl(),
      });
      count++;
    }
  } catch (err) {
    Logger.log("Error in getModifiedFiles: " + err);
  }
  return files;
}

/**
 * Get files recently shared with the user.
 */
function getRecentlyShared(cutoffDate) {
  const dateStr = Utilities.formatDate(cutoffDate, Session.getScriptTimeZone(), "yyyy-MM-dd");
  const query = "sharedWithMe = true and modifiedDate > '" + dateStr + "' and trashed = false";

  const files = [];
  try {
    const iter = DriveApp.searchFiles(query);
    let count = 0;
    while (iter.hasNext() && count < 30) {
      const file = iter.next();
      files.push({
        name: file.getName(),
        type: mimeToType(file.getMimeType()),
        shared_by: file.getSharingAccess().toString(),
        date: file.getLastUpdated().toISOString(),
        link: file.getUrl(),
      });
      count++;
    }
  } catch (err) {
    Logger.log("Error in getRecentlyShared: " + err);
  }
  return files;
}

/**
 * Try to get the last editor of a file.
 */
function getLastEditor(file) {
  try {
    const editors = file.getEditors();
    if (editors.length > 0) {
      return editors[editors.length - 1].getName();
    }
  } catch (e) {
    // Some files don't support getEditors
  }
  return "Unknown";
}

// ========== NEWSLETTER DOC CREATION ==========

function createNewsletterDoc(title, markdownContent) {
  const folder = getOrCreateFolder(CONFIG.OUTPUT_FOLDER_NAME);
  const doc = DocumentApp.create(title);
  const docFile = DriveApp.getFileById(doc.getId());

  folder.addFile(docFile);
  DriveApp.getRootFolder().removeFile(docFile);

  const body = doc.getBody();
  body.clear();

  const lines = markdownContent.split("\n");

  for (const line of lines) {
    if (line.startsWith("# ")) {
      body.appendParagraph(line.substring(2))
        .setHeading(DocumentApp.ParagraphHeading.HEADING1);
    } else if (line.startsWith("## ")) {
      body.appendParagraph(line.substring(3))
        .setHeading(DocumentApp.ParagraphHeading.HEADING2);
    } else if (line.startsWith("### ")) {
      body.appendParagraph(line.substring(4))
        .setHeading(DocumentApp.ParagraphHeading.HEADING3);
    } else if (line.startsWith("---")) {
      body.appendHorizontalRule();
    } else if (line.startsWith("- ")) {
      const item = body.appendListItem(line.substring(2));
      item.setGlyphType(DocumentApp.GlyphType.BULLET);
      applyInlineBold(item);
    } else if (line.startsWith("| ") && !line.startsWith("|-")) {
      const cells = line.split("|").filter(function(c) { return c.trim(); }).map(function(c) { return c.trim(); });
      var para = body.appendParagraph(cells.join("  |  "));
      para.setAttributes({});
      para.editAsText().setFontFamily("Courier New").setFontSize(9);
    } else if (line.trim() === "") {
      body.appendParagraph("");
    } else {
      const para = body.appendParagraph(line);
      applyInlineBold(para);
    }
  }

  doc.saveAndClose();
  return doc.getUrl();
}

function applyInlineBold(element) {
  const text = element.editAsText();
  const content = text.getText();
  const regex = /\*\*(.+?)\*\*/g;
  let match;
  const matches = [];
  while ((match = regex.exec(content)) !== null) {
    matches.push({ start: match.index, end: match.index + match[0].length - 1, inner: match[1] });
  }
  for (let i = matches.length - 1; i >= 0; i--) {
    const m = matches[i];
    text.deleteText(m.end - 1, m.end);
    text.deleteText(m.start, m.start + 1);
    text.setBold(m.start, m.start + m.inner.length - 1, true);
  }
}

// ========== UTILITIES ==========

function getOrCreateFolder(folderName) {
  const folders = DriveApp.getFoldersByName(folderName);
  if (folders.hasNext()) {
    return folders.next();
  }
  return DriveApp.createFolder(folderName);
}

function mimeToType(mimeType) {
  const mapping = {
    "application/vnd.google-apps.document": "Google Doc",
    "application/vnd.google-apps.spreadsheet": "Google Sheet",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/vnd.google-apps.form": "Google Form",
    "application/pdf": "PDF",
  };
  return mapping[mimeType] || "File";
}

// ========== TESTING ==========

function testDriveActivity() {
  const activity = getDriveActivity();
  Logger.log("Modified files: " + activity.modified_files.length);
  Logger.log("Shared with me: " + activity.shared_with_me.length);
  if (activity.modified_files.length > 0) {
    Logger.log("First file: " + activity.modified_files[0].name);
  }
  Logger.log("Success!");
}

function testCreateDoc() {
  const sampleContent = "# Test Newsletter\n\n## Section 1\n\n- **Bold item** with detail\n- Regular item\n\n## Section 2\n\nSome paragraph text here.\n\n---\n\n*Generated by PM Newsletter Bot*";
  const url = createNewsletterDoc("Test Newsletter — " + new Date().toLocaleDateString(), sampleContent);
  Logger.log("Created doc: " + url);
}
