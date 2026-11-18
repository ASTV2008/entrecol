const page = document.body.dataset.page;
let csrfToken = "";
let currentUser = null;

const authMessage = document.querySelector("#auth-message");
const authDescription = document.querySelector("#auth-description");
const authTitle = document.querySelector("#auth-title");

async function requestJson(path, options = {}) {
  const headers = new Headers(options.headers ?? {});
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET" && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (response.status === 401 && page === "reports") {
    window.location.replace("/login.html");
    throw new Error("Tu sesión terminó. Inicia sesión de nuevo.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Error HTTP ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

function showAuthMessage(message = "") {
  if (authMessage) authMessage.textContent = message;
}

function setFlow(state) {
  if (page !== "login") return;
  for (const element of document.querySelectorAll("[data-flow]")) {
    element.hidden = element.dataset.flow !== state;
  }
  showAuthMessage("");
  if (state === "login") {
    authTitle.textContent = "Iniciar sesión";
    authDescription.textContent = "Ingresa con el correo y la contraseña asignados por un administrador.";
  } else if (state === "password_change") {
    authTitle.textContent = "Cambia tu contraseña";
    authDescription.textContent = "Antes de continuar debes reemplazar la contraseña temporal.";
  } else if (state === "totp_setup") {
    authTitle.textContent = "Configura la autenticación multifactor";
    authDescription.textContent = "TOTP es obligatorio para acceder a los reportes.";
  } else if (state === "totp_required") {
    authTitle.textContent = "Verifica tu identidad";
    authDescription.textContent = "Ingresa el código de tu aplicación autenticadora o uno de tus códigos de recuperación.";
  } else if (state === "recovery_codes") {
    authTitle.textContent = "Autenticación configurada";
    authDescription.textContent = "La cuenta ya está protegida con autenticación multifactor.";
  }
}

async function loadTotpSetup() {
  const setup = await requestJson("/api/v1/auth/totp/setup");
  document.querySelector("#totp-qr").src = setup.qr_png_data_url;
  document.querySelector("#totp-secret").textContent = setup.secret;
  document.querySelector("#setup-code").value = "";
}

async function handleLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  try {
    const result = await requestJson("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: formData.get("email"),
        password: formData.get("password"),
      }),
    });
    csrfToken = result.csrf_token;
    currentUser = result.user;
    setFlow(result.state);
    if (result.state === "totp_setup") await loadTotpSetup();
  } catch (error) {
    showAuthMessage(error.message);
  }
}

async function handlePasswordChange(event) {
  event.preventDefault();
  const values = new FormData(event.currentTarget);
  try {
    const result = await requestJson("/api/v1/auth/password/change", {
      method: "POST",
      body: JSON.stringify({
        new_password: values.get("new_password"),
        confirm_password: values.get("confirm_password"),
      }),
    });
    csrfToken = result.csrf_token;
    currentUser = result.user;
    setFlow(result.state);
    if (result.state === "totp_setup") await loadTotpSetup();
  } catch (error) {
    showAuthMessage(error.message);
  }
}

async function handleTotpVerification(event) {
  event.preventDefault();
  const values = new FormData(event.currentTarget);
  try {
    const result = await requestJson("/api/v1/auth/totp/verify", {
      method: "POST",
      body: JSON.stringify({ code: values.get("code") }),
    });
    csrfToken = result.csrf_token;
    currentUser = result.user;
    if (result.recovery_codes?.length) {
      const list = document.querySelector("#recovery-codes-list");
      list.replaceChildren();
      for (const code of result.recovery_codes) {
        const item = document.createElement("li");
        const value = document.createElement("code");
        value.textContent = code;
        item.append(value);
        list.append(item);
      }
      setFlow("recovery_codes");
    } else {
      window.location.replace("/");
    }
  } catch (error) {
    showAuthMessage(error.message);
  }
}

function roleName(role) {
  return role === "admin" ? "Administrador" : "Lector de reportes";
}

function createCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value ?? "—";
  row.append(cell);
  return cell;
}

async function refreshUsers() {
  const users = await requestJson("/api/v1/auth/admin/users");
  const userRows = document.querySelector("#user-rows");
  userRows.replaceChildren();

  for (const user of users) {
    const row = document.createElement("tr");
    createCell(row, user.email);
    const roleCell = createCell(row, "");
    const roleSelect = document.createElement("select");
    roleSelect.setAttribute("aria-label", `Rol de ${user.email}`);
    for (const role of ["report_reader", "admin"]) {
      const option = document.createElement("option");
      option.value = role;
      option.textContent = roleName(role);
      option.selected = user.role === role;
      roleSelect.append(option);
    }
    roleCell.append(roleSelect);
    createCell(row, user.is_active ? "Activa" : "Desactivada");
    createCell(row, user.totp_enabled ? "Configurado" : "Pendiente");
    const actions = document.createElement("td");
    const saveRole = document.createElement("button");
    saveRole.className = "viewer-button table-action";
    saveRole.type = "button";
    saveRole.textContent = "Guardar rol";
    saveRole.addEventListener("click", async () => {
      try {
        await requestJson(`/api/v1/auth/admin/users/${user.id}`, {
          method: "PATCH",
          body: JSON.stringify({ role: roleSelect.value }),
        });
        await refreshUsers();
      } catch (error) {
        showAdminMessage(error.message);
      }
    });
    const toggleActive = document.createElement("button");
    toggleActive.className = "viewer-button table-action";
    toggleActive.type = "button";
    toggleActive.textContent = user.is_active ? "Desactivar" : "Activar";
    toggleActive.addEventListener("click", async () => {
      try {
        await requestJson(`/api/v1/auth/admin/users/${user.id}`, {
          method: "PATCH",
          body: JSON.stringify({ is_active: !user.is_active }),
        });
        await refreshUsers();
      } catch (error) {
        showAdminMessage(error.message);
      }
    });
    const resetPassword = document.createElement("button");
    resetPassword.className = "viewer-button table-action";
    resetPassword.type = "button";
    resetPassword.textContent = "Restablecer contraseña";
    resetPassword.addEventListener("click", async () => {
      try {
        const result = await requestJson(`/api/v1/auth/admin/users/${user.id}/reset-password`, {
          method: "POST",
        });
        showAdminMessage(
          `Contraseña temporal de ${result.user.email}: ${result.temporary_password}. ` +
          "Cópiala ahora; no volverá a mostrarse.",
        );
        await refreshUsers();
      } catch (error) {
        showAdminMessage(error.message);
      }
    });
    const resetTotp = document.createElement("button");
    resetTotp.className = "viewer-button table-action";
    resetTotp.type = "button";
    resetTotp.textContent = "Restablecer MFA";
    resetTotp.addEventListener("click", async () => {
      if (!window.confirm(`¿Restablecer el autenticador de ${user.email}?`)) return;
      try {
        await requestJson(`/api/v1/auth/admin/users/${user.id}/reset-totp`, { method: "POST" });
        showAdminMessage(`Se restableció MFA para ${user.email}; deberá enrolar un nuevo autenticador.`);
        await refreshUsers();
      } catch (error) {
        showAdminMessage(error.message);
      }
    });
    actions.append(saveRole, toggleActive, resetPassword, resetTotp);
    row.append(actions);
    userRows.append(row);
  }
}

async function refreshAudit() {
  const [users, events, retention] = await Promise.all([
    requestJson("/api/v1/auth/admin/users"),
    requestJson("/api/v1/auth/admin/audit?limit=100"),
    requestJson("/api/v1/auth/admin/audit/retention"),
  ]);
  const userDirectory = new Map(users.map((user) => [user.id, user.email]));
  const auditRows = document.querySelector("#audit-rows");
  auditRows.replaceChildren();

  for (const event of events) {
    const row = document.createElement("tr");
    createCell(row, String(event.created_at).replace("T", " "));
    createCell(row, event.event_type);
    createCell(row, userDirectory.get(event.actor_user_id) || (event.actor_user_id ? `ID ${event.actor_user_id}` : "Sistema"));
    createCell(row, userDirectory.get(event.target_user_id) || (event.target_user_id ? `ID ${event.target_user_id}` : "—"));
    createCell(row, event.resource);
    createCell(row, event.success ? "Correcto" : "Fallido");
    auditRows.append(row);
  }
  document.querySelector("#audit-retention").textContent =
    `Retención configurada: ${retention.retention_days} días (purga manual)`;
}

function showAdminMessage(message = "") {
  document.querySelector("#create-user-message").textContent = message;
}

function showAuditMessage(message = "") {
  document.querySelector("#audit-message").textContent = message;
}

async function handleCreateUser(event) {
  event.preventDefault();
  const values = new FormData(event.currentTarget);
  try {
    const result = await requestJson("/api/v1/auth/admin/users", {
      method: "POST",
      body: JSON.stringify({ email: values.get("email"), role: values.get("role") }),
    });
    showAdminMessage(
      `Cuenta creada. Contraseña temporal de ${result.user.email}: ${result.temporary_password}. ` +
      "Cópiala ahora; no volverá a mostrarse.",
    );
    event.currentTarget.reset();
    await refreshUsers();
  } catch (error) {
    showAdminMessage(error.message);
  }
}

function activateReports(session) {
  currentUser = session.user;
  csrfToken = session.csrf_token;
  document.querySelector("#reports-main").hidden = false;
  document.querySelector("#page-footer").hidden = false;
  document.querySelector("#session-controls").hidden = false;
  document.querySelector("#session-identity").textContent =
    `${currentUser.email} · ${roleName(currentUser.role)}`;
  const isAdmin = currentUser.role === "admin";
  document.querySelector("#nav-admin").hidden = !isAdmin;
  document.querySelector("#nav-audit").hidden = !isAdmin;
  document.querySelector("#section-admin").hidden = !isAdmin;
  document.querySelector("#section-audit").hidden = !isAdmin;
  activateSection("reports");
}

function activateSection(name) {
  if ((name === "admin" || name === "audit") && currentUser?.role !== "admin") return;
  for (const section of document.querySelectorAll(".dashboard-section")) {
    section.hidden = section.id !== `section-${name}`;
  }
  for (const link of document.querySelectorAll("[data-section-target]")) {
    if (link.dataset.sectionTarget === name) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
  if (name === "admin") {
    void refreshUsers().catch((error) => showAdminMessage(error.message));
  } else if (name === "audit") {
    void refreshAudit().catch((error) => showAuditMessage(error.message));
  }
}

async function handleLogout() {
  try {
    await requestJson("/api/v1/auth/logout", { method: "POST" });
    window.location.replace("/login.html");
  } catch (error) {
    const message = document.querySelector("#session-message");
    message.textContent = error.message;
    message.hidden = false;
  }
}

function initializeLoginPage() {
  document.querySelector("#login-form").addEventListener("submit", handleLogin);
  document.querySelector("#password-change-form").addEventListener("submit", handlePasswordChange);
  document.querySelector("#totp-setup-form").addEventListener("submit", handleTotpVerification);
  document.querySelector("#totp-login-form").addEventListener("submit", handleTotpVerification);
  document.querySelector("#recovery-saved").addEventListener("change", (event) => {
    document.querySelector("#continue-after-enrollment").disabled = !event.currentTarget.checked;
  });
  document.querySelector("#continue-after-enrollment").addEventListener("click", () => {
    window.location.replace("/");
  });
  setFlow("login");
}

function initializeReportsPage() {
  document.querySelector("#logout-button").addEventListener("click", handleLogout);
  document.querySelector("#refresh-admin").addEventListener("click", () => {
    void refreshUsers().catch((error) => showAdminMessage(error.message));
  });
  document.querySelector("#refresh-audit").addEventListener("click", () => {
    void refreshAudit().catch((error) => showAuditMessage(error.message));
  });
  for (const link of document.querySelectorAll("[data-section-target]")) {
    link.addEventListener("click", () => activateSection(link.dataset.sectionTarget));
  }
  document.querySelector("#create-user-form").addEventListener("submit", handleCreateUser);
  document.querySelector("#account-password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const message = document.querySelector("#account-message");
    try {
      const result = await requestJson("/api/v1/auth/password/change", {
        method: "POST",
        body: JSON.stringify({
          current_password: values.get("current_password"),
          new_password: values.get("new_password"),
          confirm_password: values.get("confirm_password"),
        }),
      });
      csrfToken = result.csrf_token;
      event.currentTarget.reset();
      message.textContent = "Contraseña actualizada.";
    } catch (error) {
      message.textContent = error.message;
    }
  });
  document.querySelector("#rotate-recovery-codes").addEventListener("click", async () => {
    const code = document.querySelector("#recovery-totp-code");
    const display = document.querySelector("#recovery-codes-display");
    const message = document.querySelector("#account-message");
    try {
      const result = await requestJson("/api/v1/auth/recovery-codes", {
        method: "POST",
        body: JSON.stringify({ code: code.value }),
      });
      display.textContent = result.recovery_codes.join("\n");
      display.hidden = false;
      code.value = "";
      message.textContent = "Guarda estos códigos ahora; no volverán a mostrarse.";
    } catch (error) {
      message.textContent = error.message;
    }
  });
}

async function initialize() {
  if (page === "login") initializeLoginPage();
  else initializeReportsPage();
  try {
    const session = await requestJson("/api/v1/auth/me");
    csrfToken = session.csrf_token;
    currentUser = session.user;
    if (page === "reports") {
      if (session.state !== "active") {
        window.location.replace("/login.html");
        return;
      }
      activateReports(session);
    } else if (session.state === "active") {
      window.location.replace("/");
    } else {
      setFlow(session.state);
      if (session.state === "totp_setup") await loadTotpSetup();
    }
  } catch (error) {
    if (page === "reports") {
      window.location.replace("/login.html");
    } else {
      setFlow("login");
    }
  }
}

void initialize();
