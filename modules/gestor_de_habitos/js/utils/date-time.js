const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME_PATTERN = /^(?:[01]\d|2[0-3]):[0-5]\d$/;

const monthFormatter = new Intl.DateTimeFormat("es-MX", { month: "long", year: "numeric" });
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

// Se construye en calendario local para evitar desplazamientos de día por UTC.
export function dateKeyToLocalDate(dateKey) {
    const match = DATE_PATTERN.exec(dateKey);
    if (!match) return null;
    const [, year, month, day] = match;
    const date = new Date(Number(year), Number(month) - 1, Number(day));
    return formatDateKey(date) === dateKey ? date : null;
}

export function isValidDateKey(dateKey) {
    return dateKeyToLocalDate(dateKey) !== null;
}

export function addDays(dateKey, dayCount) {
    const date = dateKeyToLocalDate(dateKey);
    if (!date || !Number.isInteger(dayCount)) return null;
    date.setDate(date.getDate() + dayCount);
    return formatDateKey(date);
}

export function getIsoWeekday(dateKey) {
    const date = dateKeyToLocalDate(dateKey);
    if (!date) return null;
    return date.getDay() === 0 ? 7 : date.getDay();
}

export function getMonthStart(dateKey) {
    const date = dateKeyToLocalDate(dateKey);
    if (!date) return null;
    return formatDateKey(new Date(date.getFullYear(), date.getMonth(), 1));
}

export function getMonthEnd(dateKey, monthOffset = 0) {
    const date = dateKeyToLocalDate(dateKey);
    if (!date || !Number.isInteger(monthOffset)) return null;
    return formatDateKey(new Date(date.getFullYear(), date.getMonth() + monthOffset + 1, 0));
}

export function isDateInRange(dateKey, rangeStart, rangeEnd) {
    return dateKey >= rangeStart && dateKey <= rangeEnd;
}

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

// Los intervalos semiabiertos permiten que uno termine justo cuando inicia el siguiente.
export function timeRangesOverlap(firstStart, firstEnd, secondStart, secondEnd) {
    const firstStartMinutes = timeToMinutes(firstStart);
    const firstEndMinutes = timeToMinutes(firstEnd);
    const secondStartMinutes = timeToMinutes(secondStart);
    const secondEndMinutes = timeToMinutes(secondEnd);
    if ([firstStartMinutes, firstEndMinutes, secondStartMinutes, secondEndMinutes].includes(null)) {
        return false;
    }
    return firstStartMinutes < secondEndMinutes && firstEndMinutes > secondStartMinutes;
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
