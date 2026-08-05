const TIME_PATTERN = /^(?:[01]\d|2[0-3]):[0-5]\d$/;

const monthFormatter = new Intl.DateTimeFormat("es-MX", {
    month: "long",
    year: "numeric",
});
const selectedDateFormatter = new Intl.DateTimeFormat("es-MX", {
    weekday: "long",
    day: "numeric",
    month: "long",
});
const shortWeekdayFormatter = new Intl.DateTimeFormat("es-MX", { weekday: "short" });
const longWeekdayFormatter = new Intl.DateTimeFormat("es-MX", { weekday: "long" });

export function formatDateKey(date) {
    return [
        date.getFullYear(),
        String(date.getMonth() + 1).padStart(2, "0"),
        String(date.getDate()).padStart(2, "0"),
    ].join("-");
}

// Las fechas locales evitan que una conversión UTC desplace la columna del día.
export function getMonthDates(year, month) {
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    return Array.from({ length: daysInMonth }, (_, index) => new Date(year, month, index + 1));
}

export function isSameLocalDate(firstDate, secondDate) {
    return formatDateKey(firstDate) === formatDateKey(secondDate);
}

export function formatMonth(date) {
    return monthFormatter.format(date);
}

export function formatSelectedDate(date) {
    return selectedDateFormatter.format(date);
}

export function getWeekdayLabels(date) {
    return {
        short: shortWeekdayFormatter.format(date).replace(".", "").slice(0, 3),
        long: longWeekdayFormatter.format(date),
    };
}

export function timeToMinutes(time) {
    if (!TIME_PATTERN.test(time)) return null;
    const [hours, minutes] = time.split(":").map(Number);
    return hours * 60 + minutes;
}

export function isValidTimeRange(startTime, endTime) {
    const startMinutes = timeToMinutes(startTime);
    const endMinutes = timeToMinutes(endTime);
    return startMinutes !== null && endMinutes !== null && endMinutes > startMinutes;
}

export function calculateDuration(startTime, endTime) {
    if (!isValidTimeRange(startTime, endTime)) return "—";

    const totalMinutes = timeToMinutes(endTime) - timeToMinutes(startTime);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;

    if (hours && minutes) return `${hours}h ${minutes}min`;
    if (hours) return `${hours}h`;
    return `${minutes}min`;
}
