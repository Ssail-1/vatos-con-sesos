const monthNameElement = document.getElementById("monthName");
const selectedDateLabelElement = document.getElementById("selectedDateLabel");
const previousDayButton = document.getElementById("previousDayButton");
const nextDayButton = document.getElementById("nextDayButton");
const matrixHead = document.getElementById("matrixHead");
const matrixBody = document.getElementById("matrixBody");
const statusLegend = document.getElementById("statusLegend");

const currentDate = new Date();
const currentYear = currentDate.getFullYear();
const currentMonth = currentDate.getMonth();
let selectedDate = new Date(currentYear, currentMonth, currentDate.getDate());

const monthFormatter = new Intl.DateTimeFormat("es-MX", { month: "long", year: "numeric" });
const selectedDateFormatter = new Intl.DateTimeFormat("es-MX", {
    weekday: "long",
    day: "numeric",
    month: "long",
});
const weekdayFormatter = new Intl.DateTimeFormat("es-MX", { weekday: "short" });

function formatDateKey(date) {
    return [
        date.getFullYear(),
        String(date.getMonth() + 1).padStart(2, "0"),
        String(date.getDate()).padStart(2, "0"),
    ].join("-");
}

// Crea todas las fechas del mes local sin conversiones UTC que puedan desplazar el día.
function getCurrentMonthDates() {
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    return Array.from({ length: daysInMonth }, function createDate(_, index) {
        return new Date(currentYear, currentMonth, index + 1);
    });
}

function isSameLocalDate(firstDate, secondDate) {
    return formatDateKey(firstDate) === formatDateKey(secondDate);
}

function calculateDuration(startTime, endTime) {
    const [startHour, startMinute] = startTime.split(":").map(Number);
    const [endHour, endMinute] = endTime.split(":").map(Number);
    const totalMinutes = endHour * 60 + endMinute - (startHour * 60 + startMinute);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;

    if (hours && minutes) return `${hours}h ${minutes}min`;
    if (hours) return `${hours}h`;
    return `${minutes}min`;
}

function getSortedActivities() {
    return [...mockActivities].sort(function compareActivities(firstActivity, secondActivity) {
        return (
            firstActivity.plannedStartTime.localeCompare(secondActivity.plannedStartTime) ||
            firstActivity.position - secondActivity.position
        );
    });
}

function createTextCell(tagName, className, text) {
    const cell = document.createElement(tagName);
    cell.className = className;
    cell.textContent = text;
    return cell;
}

function getDateLabel(date) {
    return selectedDateFormatter.format(date);
}

function createStatusButton(activity, date) {
    const dateKey = formatDateKey(date);
    const button = document.createElement("button");
    const status = activity.statesByDate[dateKey] || "pending";

    button.type = "button";
    button.className = "status-button";
    button.dataset.activityId = activity.id;
    button.dataset.date = dateKey;
    updateStatusControl(button, status, activity.name, getDateLabel(date));

    button.addEventListener("click", function changeActivityStatus() {
        const currentStatus = activity.statesByDate[dateKey] || "pending";
        const nextStatus = getNextStatus(currentStatus);
        activity.statesByDate[dateKey] = nextStatus;
        updateStatusControl(button, nextStatus, activity.name, getDateLabel(date));
    });

    return button;
}

function createDayHeader(date) {
    const dateKey = formatDateKey(date);
    const header = document.createElement("th");
    const heading = document.createElement("span");
    const weekday = document.createElement("abbr");
    const dayNumber = document.createElement("span");

    header.scope = "col";
    header.className = "day-column";
    header.dataset.date = dateKey;
    heading.className = "day-heading";
    weekday.textContent = weekdayFormatter.format(date).replace(".", "").slice(0, 3);
    weekday.title = new Intl.DateTimeFormat("es-MX", { weekday: "long" }).format(date);
    dayNumber.textContent = String(date.getDate());

    if (isSameLocalDate(date, currentDate)) header.classList.add("today-column");
    if (isSameLocalDate(date, selectedDate)) header.classList.add("selected-day-column");

    heading.append(weekday, dayNumber);
    header.append(heading);
    return header;
}

function renderMatrixHeader(monthDates) {
    const row = document.createElement("tr");
    row.append(
        createTextCell("th", "position-column", "#"),
        createTextCell("th", "time-column", "Inicio"),
        createTextCell("th", "duration-column", "Duración"),
        createTextCell("th", "name-column", "Actividad"),
    );

    row.children[0].scope = "col";
    row.children[1].scope = "col";
    row.children[2].scope = "col";
    row.children[3].scope = "col";
    monthDates.forEach(function appendDateHeader(date) {
        row.append(createDayHeader(date));
    });

    matrixHead.replaceChildren(row);
}

function createActivityRow(activity, monthDates) {
    const row = document.createElement("tr");
    const nameCell = createTextCell("th", "name-column activity-name", activity.name);
    nameCell.scope = "row";

    row.append(
        createTextCell("td", "position-column activity-position", activity.position),
        createTextCell("td", "time-column activity-time", activity.plannedStartTime),
        createTextCell(
            "td",
            "duration-column activity-duration",
            calculateDuration(activity.plannedStartTime, activity.plannedEndTime),
        ),
        nameCell,
    );

    monthDates.forEach(function appendStatusCell(date) {
        const cell = document.createElement("td");
        cell.className = "day-column";
        cell.dataset.date = formatDateKey(date);
        if (isSameLocalDate(date, currentDate)) cell.classList.add("today-column");
        if (isSameLocalDate(date, selectedDate)) cell.classList.add("selected-day-column");
        cell.append(createStatusButton(activity, date));
        row.append(cell);
    });

    return row;
}

function renderActivities(monthDates) {
    const fragment = document.createDocumentFragment();
    getSortedActivities().forEach(function appendActivity(activity) {
        fragment.append(createActivityRow(activity, monthDates));
    });
    matrixBody.replaceChildren(fragment);
}

function renderStatusLegend() {
    const fragment = document.createDocumentFragment();
    activityStates.forEach(function appendLegendItem(status) {
        const item = document.createElement("li");
        const symbol = document.createElement("span");
        const label = document.createElement("span");
        const definition = statusDefinitions[status];

        item.className = "legend-item";
        symbol.className = "legend-symbol";
        symbol.style.setProperty("--legend-color", definition.color);
        symbol.textContent = definition.symbol;
        symbol.setAttribute("aria-hidden", "true");
        label.textContent = definition.label;
        item.append(symbol, label);
        fragment.append(item);
    });
    statusLegend.replaceChildren(fragment);
}

function updateSelectedDatePresentation() {
    const selectedDateKey = formatDateKey(selectedDate);
    document.querySelectorAll(".selected-day-column").forEach(function clearSelectedColumn(element) {
        element.classList.remove("selected-day-column");
    });
    document.querySelectorAll(`[data-date="${selectedDateKey}"]`).forEach(function markSelectedColumn(element) {
        element.classList.add("selected-day-column");
    });

    selectedDateLabelElement.textContent = getDateLabel(selectedDate);
    previousDayButton.disabled = selectedDate.getDate() === 1;
    nextDayButton.disabled =
        selectedDate.getDate() === new Date(currentYear, currentMonth + 1, 0).getDate();
}

function moveSelectedDate(dayDifference) {
    const candidate = new Date(currentYear, currentMonth, selectedDate.getDate() + dayDifference);
    if (candidate.getMonth() !== currentMonth) return;
    selectedDate = candidate;
    updateSelectedDatePresentation();
}

function initializeApplication() {
    const monthDates = getCurrentMonthDates();
    monthNameElement.textContent = monthFormatter.format(currentDate);
    renderMatrixHeader(monthDates);
    renderActivities(monthDates);
    renderStatusLegend();
    updateSelectedDatePresentation();

    previousDayButton.addEventListener("click", function showPreviousDay() {
        moveSelectedDate(-1);
    });
    nextDayButton.addEventListener("click", function showNextDay() {
        moveSelectedDate(1);
    });
}

initializeApplication();
