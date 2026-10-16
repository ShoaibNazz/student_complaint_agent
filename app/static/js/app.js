document.addEventListener("DOMContentLoaded", function () {
  // Character counters for textareas
  document.querySelectorAll("textarea[data-counter]").forEach(function (ta) {
    var out = document.getElementById(ta.dataset.counter);
    var update = function () { if (out) out.textContent = ta.value.length; };
    ta.addEventListener("input", update);
    update();
  });

  // Confirmation dialogs for forms
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // ==================== Authentication Page Logic ====================
  var authCard = document.getElementById("authCard");
  if (!authCard) return;

  var loginSection = document.getElementById("loginSection");
  var registerSection = document.getElementById("registerSection");
  var forgotSection = document.getElementById("forgotSection");
  var resetSection = document.getElementById("resetSection");
  var tabBtnLogin = document.getElementById("tabBtnLogin");
  var tabBtnRegister = document.getElementById("tabBtnRegister");
  var subtitle = document.getElementById("authCardSubtitle");

  function clearAuthAlerts() {
    var cErr = document.getElementById("clientErrorAlert");
    if (cErr) {
      cErr.classList.add("d-none");
      cErr.classList.remove("d-flex");
    }
    var sErr = document.getElementById("serverErrorAlert");
    if (sErr) sErr.classList.add("d-none");
    var sOk = document.getElementById("serverSuccessAlert");
    if (sOk) sOk.classList.add("d-none");
  }

  function showAuthError(msg) {
    var cErr = document.getElementById("clientErrorAlert");
    var cMsg = document.getElementById("clientErrorMessage");
    if (cErr && cMsg) {
      cMsg.textContent = msg;
      cErr.classList.remove("d-none");
      cErr.classList.add("d-flex");
    }
  }

  function switchAuthTab(tab) {
    clearAuthAlerts();

    if (loginSection) loginSection.classList.add("d-none");
    if (registerSection) registerSection.classList.add("d-none");
    if (forgotSection) forgotSection.classList.add("d-none");
    if (resetSection) resetSection.classList.add("d-none");

    if (tab === "register") {
      if (registerSection) registerSection.classList.remove("d-none");
      if (tabBtnRegister) tabBtnRegister.classList.add("active");
      if (tabBtnLogin) tabBtnLogin.classList.remove("active");
      authCard.classList.add("is-register");
      if (subtitle) subtitle.textContent = "Sign in or register to continue";
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", "/register");
      }
    } else if (tab === "forgot") {
      if (forgotSection) forgotSection.classList.remove("d-none");
      if (tabBtnLogin) tabBtnLogin.classList.add("active");
      if (tabBtnRegister) tabBtnRegister.classList.remove("active");
      authCard.classList.remove("is-register");
      if (subtitle) subtitle.textContent = "Recover your portal account password";
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", "/forgot-password");
      }
    } else if (tab === "reset") {
      if (resetSection) resetSection.classList.remove("d-none");
      if (tabBtnLogin) tabBtnLogin.classList.add("active");
      if (tabBtnRegister) tabBtnRegister.classList.remove("active");
      authCard.classList.remove("is-register");
      if (subtitle) subtitle.textContent = "Create a new password for your account";
    } else {
      if (loginSection) loginSection.classList.remove("d-none");
      if (tabBtnLogin) tabBtnLogin.classList.add("active");
      if (tabBtnRegister) tabBtnRegister.classList.remove("active");
      authCard.classList.remove("is-register");
      if (subtitle) subtitle.textContent = "Sign in or register to continue";
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", "/login");
      }
    }
  }

  window.switchAuthTab = switchAuthTab;

  if (tabBtnLogin) {
    tabBtnLogin.addEventListener("click", function (e) {
      e.preventDefault();
      switchAuthTab("login");
    });
  }

  if (tabBtnRegister) {
    tabBtnRegister.addEventListener("click", function (e) {
      e.preventDefault();
      switchAuthTab("register");
    });
  }

  var forgotLink = document.getElementById("forgotPasswordLink");
  if (forgotLink) {
    forgotLink.addEventListener("click", function (e) {
      e.preventDefault();
      switchAuthTab("forgot");
    });
  }

  document.querySelectorAll(".back-to-login-link").forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      switchAuthTab("login");
    });
  });

  // Password eye visibility toggle
  document.querySelectorAll(".auth-eye-toggle").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var targetId = this.getAttribute("data-target");
      var input = document.getElementById(targetId);
      if (!input) return;
      var icon = this.querySelector("i");
      if (input.type === "password") {
        input.type = "text";
        if (icon) {
          icon.classList.remove("bi-eye");
          icon.classList.add("bi-eye-slash");
        }
      } else {
        input.type = "password";
        if (icon) {
          icon.classList.remove("bi-eye-slash");
          icon.classList.add("bi-eye");
        }
      }
    });
  });

  // Form validation
  var loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", function (e) {
      clearAuthAlerts();
      var acc = document.getElementById("loginAccountType");
      var camp = document.getElementById("loginCampus");
      var ident = document.getElementById("loginIdentifier");
      var pwd = document.getElementById("loginPassword");
      if (!acc || !acc.value) {
        e.preventDefault();
        showAuthError("Please select your account type.");
        if (acc) acc.focus();
        return false;
      }
      if (!camp || !camp.value) {
        e.preventDefault();
        showAuthError("Please select your registered campus.");
        if (camp) camp.focus();
        return false;
      }
      if (!ident || !ident.value.trim() || !pwd || !pwd.value) {
        e.preventDefault();
        showAuthError("Please enter your email address/user ID and password.");
        return false;
      }
    });
  }

  // Dynamic Registration Form Fields by Account Type (Student / Employee / Admin)
  var registerAccountType = document.getElementById("registerAccountType");
  var studentProgramGroup = document.getElementById("studentProgramGroup");
  var registerProgram = document.getElementById("registerProgram");
  var employeeRoleGroup = document.getElementById("employeeRoleGroup");
  var registerEmployeeRole = document.getElementById("registerEmployeeRole");
  var employeeDepartmentGroup = document.getElementById("employeeDepartmentGroup");
  var registerDepartment = document.getElementById("registerDepartment");
  var adminRoleGroup = document.getElementById("adminRoleGroup");
  var registerAdminRole = document.getElementById("registerAdminRole");
  var registerIdentifier = document.getElementById("registerIdentifier");
  var registerEmail = document.getElementById("registerEmail");

  function setGroupVisible(groupEl, inputEl, isVisible, isRequired) {
    if (groupEl) {
      if (isVisible) {
        groupEl.classList.remove("d-none");
      } else {
        groupEl.classList.add("d-none");
      }
    }
    if (inputEl) {
      inputEl.disabled = !isVisible;
      inputEl.required = Boolean(isVisible && isRequired);
    }
  }

  function syncRegisterAccountFields() {
    if (!registerAccountType) return;
    var accType = (registerAccountType.value || "").toUpperCase();

    setGroupVisible(studentProgramGroup, registerProgram, accType === "STUDENT", true);
    setGroupVisible(employeeRoleGroup, registerEmployeeRole, accType === "EMPLOYEE", true);
    setGroupVisible(employeeDepartmentGroup, registerDepartment, accType === "EMPLOYEE", true);
    setGroupVisible(adminRoleGroup, registerAdminRole, accType === "ADMIN", false);

    if (registerAdminRole && accType === "ADMIN") {
      registerAdminRole.value = "Admin";
    }

    if (registerIdentifier) {
      if (accType === "STUDENT") {
        registerIdentifier.placeholder = "Enter student ID or registration number";
      } else if (accType === "EMPLOYEE") {
        registerIdentifier.placeholder = "Enter official employee ID";
      } else if (accType === "ADMIN") {
        registerIdentifier.placeholder = "Enter administrator ID";
      } else {
        registerIdentifier.placeholder = "Enter student, employee, or admin ID";
      }
    }

    if (registerEmail) {
      if (accType === "EMPLOYEE") {
        registerEmail.placeholder = "Enter official email address";
      } else if (accType === "ADMIN") {
        registerEmail.placeholder = "Enter administrator email address";
      } else {
        registerEmail.placeholder = "Enter your email address";
      }
    }
  }

  if (registerAccountType) {
    registerAccountType.addEventListener("change", function () {
      clearAuthAlerts();
      syncRegisterAccountFields();
    });
    syncRegisterAccountFields();
  }

  var registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", function (e) {
      clearAuthAlerts();
      var acc = document.getElementById("registerAccountType");
      var name = document.getElementById("registerFullName");
      var ident = document.getElementById("registerIdentifier");
      var email = document.getElementById("registerEmail");
      var pwd = document.getElementById("registerPassword");

      if (!acc || !acc.value) {
        e.preventDefault();
        showAuthError("Please select your account type.");
        if (acc) acc.focus();
        return false;
      }
      var accType = acc.value.toUpperCase();

      if (!name || !name.value.trim()) {
        e.preventDefault();
        showAuthError("Please enter your full name.");
        if (name) name.focus();
        return false;
      }
      if (!ident || !ident.value.trim()) {
        e.preventDefault();
        if (accType === "STUDENT") {
          showAuthError("Please enter your student ID or registration number.");
        } else if (accType === "EMPLOYEE") {
          showAuthError("Please enter your official employee ID.");
        } else {
          showAuthError("Please enter your administrator ID.");
        }
        if (ident) ident.focus();
        return false;
      }
      var emailVal = email ? email.value.trim() : "";
      if (!emailVal || emailVal.indexOf("@") === -1 || emailVal.split("@").pop().indexOf(".") === -1) {
        e.preventDefault();
        showAuthError("Please enter a valid email address.");
        if (email) email.focus();
        return false;
      }

      var campus = document.getElementById("registerCampus");
      if (!campus || !campus.value) {
        e.preventDefault();
        showAuthError("Please select your Campus.");
        if (campus) campus.focus();
        return false;
      }

      if (accType === "STUDENT") {
        if (!registerProgram || !registerProgram.value) {
          e.preventDefault();
          showAuthError("Please select your Degree/Program.");
          if (registerProgram) registerProgram.focus();
          return false;
        }
      } else if (accType === "EMPLOYEE") {
        if (!registerEmployeeRole || !registerEmployeeRole.value) {
          e.preventDefault();
          showAuthError("Please select your Role (Professor, Head of Department (HOD), or Principal).");
          if (registerEmployeeRole) registerEmployeeRole.focus();
          return false;
        }
        if (!registerDepartment || !registerDepartment.value) {
          e.preventDefault();
          showAuthError("Please select your Department.");
          if (registerDepartment) registerDepartment.focus();
          return false;
        }
      } else if (accType === "ADMIN") {
        if (registerAdminRole) {
          registerAdminRole.value = "Admin";
        }
      }

      var cpwd = document.getElementById("registerConfirmPassword");
      if (!pwd || pwd.value.length < 6) {
        e.preventDefault();
        showAuthError("Password must be at least 6 characters.");
        if (pwd) pwd.focus();
        return false;
      }

      if (!cpwd || cpwd.value !== pwd.value) {
        e.preventDefault();
        showAuthError("Passwords do not match.");
        if (cpwd) cpwd.focus();
        return false;
      }
    });
  }

  var forgotForm = document.getElementById("forgotForm");
  if (forgotForm) {
    forgotForm.addEventListener("submit", function (e) {
      clearAuthAlerts();
      var email = document.getElementById("forgotEmail");
      var emailVal = email ? email.value.trim() : "";
      if (!emailVal || emailVal.indexOf("@") === -1 || emailVal.split("@").pop().indexOf(".") === -1) {
        e.preventDefault();
        showAuthError("Please enter your registered email address.");
        if (email) email.focus();
        return false;
      }
    });
  }

  var resetForm = document.getElementById("resetForm");
  if (resetForm) {
    resetForm.addEventListener("submit", function (e) {
      clearAuthAlerts();
      var p1 = document.getElementById("resetNewPassword");
      var p2 = document.getElementById("resetConfirmPassword");
      if (!p1 || p1.value.length < 6) {
        e.preventDefault();
        showAuthError("New password must be at least 6 characters.");
        if (p1) p1.focus();
        return false;
      }
      if (!p2 || p1.value !== p2.value) {
        e.preventDefault();
        showAuthError("New passwords do not match.");
        if (p2) p2.focus();
        return false;
      }
    });
  }

  /* ========================================================================
     Submit Complaint Form (Reference Image 2 UI & Dynamic Behavior)
     ======================================================================== */
  var complaintForm = document.getElementById("complaintSubmitForm");
  if (complaintForm) {
    var cmpAccountType = document.getElementById("cmpAccountType");
    var cmpProgramOrRole = document.getElementById("cmpProgramOrRole");
    var cmpOriginatingCampus = document.getElementById("cmpOriginatingCampus");
    var cmpTargetCampus = document.getElementById("cmpTargetCampus");
    var cmpFullName = document.getElementById("cmpFullName");
    var cmpStudentId = document.getElementById("cmpStudentId");
    var cmpEmail = document.getElementById("cmpEmail");
    var cmpTitle = document.getElementById("cmpTitle");
    var cmpDescription = document.getElementById("cmpDescription");
    var cmpAttachment = document.getElementById("cmpAttachment");
    var cmpDropzone = document.getElementById("cmpDropzone");
    var cmpDropzonePrompt = document.getElementById("cmpDropzonePrompt");
    var cmpPreviewBox = document.getElementById("cmpPreviewBox");
    var cmpPreviewImg = document.getElementById("cmpPreviewImg");
    var cmpPreviewName = document.getElementById("cmpPreviewName");
    var cmpPreviewSize = document.getElementById("cmpPreviewSize");
    var cmpReplaceBtn = document.getElementById("cmpReplaceBtn");
    var cmpRemoveBtn = document.getElementById("cmpRemoveBtn");
    var cmpSubmitBtn = document.getElementById("cmpSubmitBtn");
    var cmpSubmitIcon = document.getElementById("cmpSubmitIcon");
    var cmpSubmitSpinner = document.getElementById("cmpSubmitSpinner");
    var cmpSubmitText = document.getElementById("cmpSubmitText");

    var MAX_IMAGE_BYTES = 5 * 1024 * 1024;
    var ALLOWED_MIMES = ["image/png", "image/jpeg", "image/jpg", "image/webp"];
    var ALLOWED_EXTS = [".png", ".jpg", ".jpeg", ".webp"];

    function setFieldError(fieldName, message) {
      var errEl = document.getElementById("err-" + fieldName);
      var inputEl = complaintForm.querySelector('[name="' + fieldName + '"]');
      var groupEl = inputEl ? inputEl.closest(".cmp-input-group, .cmp-dropzone") : null;
      if (errEl) {
        errEl.textContent = message || "";
        errEl.classList.toggle("d-none", !message);
      }
      if (groupEl) {
        groupEl.classList.toggle("is-invalid-group", Boolean(message));
      }
    }

    function clearAllFieldErrors() {
      var fields = [
        "account_type",
        "originating_campus",
        "student_name",
        "target_campus",
        "student_id",
        "class_or_program",
        "email",
        "complaint_title",
        "complaint_text",
        "attachment"
      ];
      fields.forEach(function (f) {
        setFieldError(f, "");
      });
      var globalAlert = document.getElementById("cmpGlobalErrorAlert");
      if (globalAlert) {
        globalAlert.classList.add("d-none");
      }
    }

    function parseJsonAttr(el, attrName, fallback) {
      if (!el) return fallback;
      var raw = el.getAttribute(attrName);
      if (!raw) return fallback;
      try {
        return JSON.parse(raw);
      } catch (err) {
        return fallback;
      }
    }

    var degreePrograms = parseJsonAttr(cmpProgramOrRole, "data-programs", [
      "BS Computer Science",
      "BS Information Technology",
      "BS Software Engineering",
      "BS Mathematics",
      "BS Physics",
      "BS Chemistry",
      "BS Botany",
      "BS Zoology",
      "BS English",
      "BS Urdu",
      "BS Islamic Studies",
      "BS Economics",
      "BS Economics and Finance",
      "BS Business Analytics",
      "BBA (Bachelor of Business Administration)",
      "B.Ed. (Hons)",
      "B.Ed. (Hons) Special Education",
      "B.Ed. (Hons) Educational Leadership & Management",
      "B.Ed. Secondary (1.5 Years)",
      "BS Physical Education and Sports Sciences",
      "BFA Painting & Graphic Design",
      "BS History",
      "MS Computer Science",
      "MS Information Technology",
      "MS Mathematics",
      "MS Physics",
      "MS Chemistry",
      "MS Botany",
      "MS Zoology",
      "MPhil Education",
      "MPhil Educational Leadership and Policy Studies",
      "MPhil Special Education",
      "MPhil English (Linguistics)",
      "MPhil Urdu",
      "MPhil Economics",
      "MPhil Islamic Studies",
      "MBA (Master of Business Administration)",
      "MS Management Sciences",
      "PhD Computer Science",
      "PhD Education",
      "PhD Mathematics",
      "PhD Physics",
      "PhD Chemistry",
      "PhD Botany",
      "PhD Zoology",
      "PhD English (Linguistics)",
      "PhD Urdu",
      "PhD Economics",
      "PhD Management Sciences",
      "PhD Islamic Studies"
    ]);
    var employeeRoles = parseJsonAttr(cmpProgramOrRole, "data-employee-roles", [
      "Lecturer",
      "Assistant Professor",
      "Associate Professor",
      "Professor",
      "Head of Department (HOD)",
      "Principal / Campus Director",
      "Director of Division",
      "Dean",
      "Registrar / Administrative Officer",
      "Controller of Examinations",
      "Treasurer / Accounts Officer",
      "Directorate of Student Affairs Officer",
      "Directorate of IT Officer",
      "Librarian",
      "Transport Officer",
      "Hostel Warden",
      "Security Officer"
    ]);
    var universityDepts = parseJsonAttr(cmpProgramOrRole, "data-departments", [
      "Department of Information Sciences",
      "Department of Mathematics",
      "Department of Physics",
      "Department of Chemistry",
      "Department of Botany",
      "Department of Zoology",
      "Department of Education",
      "Department of Special Education",
      "Department of Educational Leadership and Policy Studies",
      "Department of STEM Education",
      "UE Business School",
      "Department of Economics",
      "Department of English",
      "Department of Urdu",
      "Department of Islamic Studies",
      "Department of History, Arts and Cultural Heritage",
      "Department of Physical Education and Sports Sciences",
      "Directorate of Student Affairs",
      "IT Department",
      "Examination Department",
      "Accounts Department",
      "Admissions Department",
      "Transport Department",
      "Hostel Administration",
      "Library Department",
      "Administration Office",
      "Academic Department",
      "Academic Administration",
      "Administration / Maintenance",
      "Security / Student Affairs",
      "Student Affairs / Designated Safeguarding Officer",
      "Student Affairs / Administration",
      "Administration / Health & Safety Officer",
      "Student Affairs"
    ]);

    function rebuildProgramOrRoleOptions(accountType, preferredValue) {
      if (!cmpProgramOrRole) return;
      var currentVal = preferredValue !== undefined ? preferredValue : cmpProgramOrRole.value;
      cmpProgramOrRole.innerHTML = "";

      var placeholderOpt = document.createElement("option");
      placeholderOpt.value = "";
      placeholderOpt.disabled = true;
      placeholderOpt.textContent = "Select Program / Role";
      cmpProgramOrRole.appendChild(placeholderOpt);

      var acc = (accountType || "").toUpperCase();
      var matched = false;

      if (acc === "STUDENT") {
        degreePrograms.forEach(function (prog) {
          var opt = document.createElement("option");
          opt.value = prog;
          opt.textContent = prog;
          if (currentVal === prog) {
            opt.selected = true;
            matched = true;
          }
          cmpProgramOrRole.appendChild(opt);
        });
      } else if (acc === "EMPLOYEE") {
        var roleGroup = document.createElement("optgroup");
        roleGroup.label = "Employee Roles";
        employeeRoles.forEach(function (role) {
          var opt = document.createElement("option");
          opt.value = role;
          opt.textContent = role;
          if (currentVal === role) {
            opt.selected = true;
            matched = true;
          }
          roleGroup.appendChild(opt);
        });
        cmpProgramOrRole.appendChild(roleGroup);

        var deptGroup = document.createElement("optgroup");
        deptGroup.label = "University Departments";
        universityDepts.forEach(function (dept) {
          var opt = document.createElement("option");
          opt.value = dept;
          opt.textContent = dept;
          if (currentVal === dept) {
            opt.selected = true;
            matched = true;
          }
          deptGroup.appendChild(opt);
        });
        cmpProgramOrRole.appendChild(deptGroup);
      } else if (acc === "ADMIN") {
        var adminOpt = document.createElement("option");
        adminOpt.value = "Admin";
        adminOpt.textContent = "Admin";
        adminOpt.selected = true;
        matched = true;
        cmpProgramOrRole.appendChild(adminOpt);
      } else {
        var stuGroup = document.createElement("optgroup");
        stuGroup.label = "Academic Programs (Student)";
        degreePrograms.forEach(function (prog) {
          var opt = document.createElement("option");
          opt.value = prog;
          opt.textContent = prog;
          if (currentVal === prog) {
            opt.selected = true;
            matched = true;
          }
          stuGroup.appendChild(opt);
        });
        cmpProgramOrRole.appendChild(stuGroup);

        var empGroup = document.createElement("optgroup");
        empGroup.label = "Employee Roles & Departments";
        employeeRoles.concat(universityDepts).forEach(function (item) {
          var opt = document.createElement("option");
          opt.value = item;
          opt.textContent = item;
          if (currentVal === item) {
            opt.selected = true;
            matched = true;
          }
          empGroup.appendChild(opt);
        });
        cmpProgramOrRole.appendChild(empGroup);

        var admGroup = document.createElement("optgroup");
        admGroup.label = "Administration";
        var admOpt = document.createElement("option");
        admOpt.value = "Admin";
        admOpt.textContent = "Admin";
        if (currentVal === "Admin") {
          admOpt.selected = true;
          matched = true;
        }
        admGroup.appendChild(admOpt);
        cmpProgramOrRole.appendChild(admGroup);
      }

      if (!matched) {
        placeholderOpt.selected = true;
      }
    }

    if (cmpAccountType) {
      cmpAccountType.addEventListener("change", function () {
        setFieldError("account_type", "");
        rebuildProgramOrRoleOptions(cmpAccountType.value, "");
      });
    }

    // Bind real-time field error clearing
    [
      ["originating_campus", cmpOriginatingCampus],
      ["target_campus", cmpTargetCampus],
      ["student_name", cmpFullName],
      ["student_id", cmpStudentId],
      ["class_or_program", cmpProgramOrRole],
      ["email", cmpEmail],
      ["complaint_title", cmpTitle],
      ["complaint_text", cmpDescription]
    ].forEach(function (pair) {
      var name = pair[0];
      var el = pair[1];
      if (!el) return;
      var evtName = el.tagName === "SELECT" ? "change" : "input";
      el.addEventListener(evtName, function () {
        if (el.value && el.value.trim()) {
          setFieldError(name, "");
        }
      });
    });

    // Image Upload & Drag-and-Drop Handling
    function formatFileSize(bytes) {
      if (bytes < 1024) return bytes + " B";
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
      return (bytes / (1024 * 1024)).toFixed(2) + " MB";
    }

    function validateImageFile(file) {
      if (!file) return "";
      var fileName = (file.name || "").toLowerCase();
      var hasValidExt = ALLOWED_EXTS.some(function (ext) {
        return fileName.endsWith(ext);
      });
      var hasValidMime = !file.type || ALLOWED_MIMES.indexOf(file.type.toLowerCase()) !== -1;
      if (!hasValidExt || !hasValidMime) {
        return "Invalid file type. Allowed formats: PNG, JPG, JPEG, WEBP.";
      }
      if (file.size <= 0) {
        return "Uploaded image file is empty.";
      }
      if (file.size > MAX_IMAGE_BYTES) {
        return "Image size exceeds the 5MB maximum limit.";
      }
      return "";
    }

    function clearSelectedImage() {
      if (cmpAttachment) {
        cmpAttachment.value = "";
      }
      if (cmpPreviewImg) {
        cmpPreviewImg.src = "";
      }
      if (cmpPreviewBox) {
        cmpPreviewBox.classList.add("d-none");
      }
      if (cmpDropzonePrompt) {
        cmpDropzonePrompt.classList.remove("d-none");
      }
      setFieldError("attachment", "");
    }

    function handleSelectedFile(file) {
      if (!file) {
        clearSelectedImage();
        return;
      }
      var errMsg = validateImageFile(file);
      if (errMsg) {
        clearSelectedImage();
        setFieldError("attachment", errMsg);
        return;
      }
      setFieldError("attachment", "");
      if (cmpPreviewName) cmpPreviewName.textContent = file.name;
      if (cmpPreviewSize) cmpPreviewSize.textContent = formatFileSize(file.size);

      var reader = new FileReader();
      reader.onload = function (ev) {
        if (cmpPreviewImg && ev.target && ev.target.result) {
          cmpPreviewImg.src = ev.target.result;
        }
      };
      reader.readAsDataURL(file);

      if (cmpDropzonePrompt) cmpDropzonePrompt.classList.add("d-none");
      if (cmpPreviewBox) cmpPreviewBox.classList.remove("d-none");
    }

    if (cmpDropzone && cmpAttachment) {
      // Accessible keyboard trigger (Enter/Space opens file picker)
      cmpDropzone.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          cmpAttachment.click();
        }
      });

      ["dragenter", "dragover"].forEach(function (evt) {
        cmpDropzone.addEventListener(evt, function (e) {
          e.preventDefault();
          e.stopPropagation();
          cmpDropzone.classList.add("drag-over");
        });
      });

      ["dragleave", "dragend", "drop"].forEach(function (evt) {
        cmpDropzone.addEventListener(evt, function (e) {
          e.preventDefault();
          e.stopPropagation();
          cmpDropzone.classList.remove("drag-over");
        });
      });

      cmpDropzone.addEventListener("drop", function (e) {
        var dt = e.dataTransfer;
        if (dt && dt.files && dt.files.length > 0) {
          var droppedFile = dt.files[0];
          var errMsg = validateImageFile(droppedFile);
          if (errMsg) {
            clearSelectedImage();
            setFieldError("attachment", errMsg);
            return;
          }
          try {
            var transfer = new DataTransfer();
            transfer.items.add(droppedFile);
            cmpAttachment.files = transfer.files;
          } catch (err) {
            // Fallback if DataTransfer constructor is restricted
          }
          handleSelectedFile(droppedFile);
        }
      });

      cmpAttachment.addEventListener("change", function () {
        var file = cmpAttachment.files && cmpAttachment.files[0] ? cmpAttachment.files[0] : null;
        handleSelectedFile(file);
      });
    }

    if (cmpReplaceBtn && cmpAttachment) {
      cmpReplaceBtn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        cmpAttachment.click();
      });
    }

    if (cmpRemoveBtn) {
      cmpRemoveBtn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        clearSelectedImage();
      });
    }

    // Client-side validation & duplicate submission prevention
    var isSubmitting = false;
    complaintForm.addEventListener("submit", function (e) {
      if (isSubmitting) {
        e.preventDefault();
        return false;
      }

      clearAllFieldErrors();
      var hasError = false;
      var firstInvalidEl = null;

      function flagInvalid(fieldName, el, msg) {
        setFieldError(fieldName, msg);
        hasError = true;
        if (!firstInvalidEl && el) {
          firstInvalidEl = el;
        }
      }

      if (!cmpAccountType || !cmpAccountType.value) {
        flagInvalid("account_type", cmpAccountType, "Please select an Account Type.");
      }
      if (!cmpOriginatingCampus || !cmpOriginatingCampus.value) {
        flagInvalid("originating_campus", cmpOriginatingCampus, "Please select an Originating Campus.");
      }
      if (!cmpFullName || !cmpFullName.value.trim() || cmpFullName.value.trim().length < 2) {
        flagInvalid("student_name", cmpFullName, "Please enter your Full Name (at least 2 characters).");
      }
      if (!cmpTargetCampus || !cmpTargetCampus.value) {
        flagInvalid("target_campus", cmpTargetCampus, "Please select a Target Campus.");
      }
      if (!cmpStudentId || !cmpStudentId.value.trim()) {
        flagInvalid("student_id", cmpStudentId, "Please enter your Student ID or Employee ID.");
      }
      if (!cmpProgramOrRole || !cmpProgramOrRole.value) {
        flagInvalid("class_or_program", cmpProgramOrRole, "Please select your Academic Program or Role.");
      }
      var emailVal = cmpEmail ? cmpEmail.value.trim() : "";
      var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailVal || !emailRegex.test(emailVal)) {
        flagInvalid("email", cmpEmail, "Please enter a valid Email Address.");
      }
      if (!cmpTitle || cmpTitle.value.trim().length < 3) {
        flagInvalid("complaint_title", cmpTitle, "Complaint Title must be at least 3 characters.");
      }
      if (!cmpDescription || cmpDescription.value.trim().length < 10) {
        flagInvalid("complaint_text", cmpDescription, "Please describe your complaint in detail (at least 10 characters).");
      }
      if (cmpAttachment && cmpAttachment.files && cmpAttachment.files[0]) {
        var attachErr = validateImageFile(cmpAttachment.files[0]);
        if (attachErr) {
          flagInvalid("attachment", cmpDropzone, attachErr);
        }
      }

      if (hasError) {
        e.preventDefault();
        if (firstInvalidEl && typeof firstInvalidEl.focus === "function") {
          firstInvalidEl.focus();
        }
        return false;
      }

      isSubmitting = true;
      if (cmpSubmitBtn) cmpSubmitBtn.disabled = true;
      if (cmpSubmitIcon) cmpSubmitIcon.classList.add("d-none");
      if (cmpSubmitSpinner) cmpSubmitSpinner.classList.remove("d-none");
      if (cmpSubmitText) cmpSubmitText.textContent = "Submitting Complaint...";
    });
  }
});

