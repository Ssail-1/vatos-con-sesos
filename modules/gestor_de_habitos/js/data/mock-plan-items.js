import { createGenerationSlotId } from "../domain/generation-slots.js";

const weekly = (days, startTime, endTime, perDayTimes = {}) => ({
    mode: "weekly",
    startDate: "2026-08-01",
    endDate: null,
    indefinite: true,
    slots: days.map((isoWeekday) => ({
        id: createGenerationSlotId(),
        isoWeekday,
        startTime: perDayTimes[String(isoWeekday)]?.startTime ?? startTime,
        endTime: perDayTimes[String(isoWeekday)]?.endTime ?? endTime,
    })),
});

// Fixtures inmutables: el store crea copias protegidas al iniciar cada sesión.
export const initialPlanItems = Object.freeze([
    {
        id: "gym-pecho",
        name: "Gym - Pecho",
        kind: "activity",
        activityType: "periodic",
        generationConfig: weekly([1, 3, 5], "05:30", "07:15", {
            "5": { startTime: "06:00", endTime: "07:30" },
        }),
    },
    {
        id: "cepillado-dientes",
        name: "Cepillado de dientes",
        kind: "habit",
        habitType: "scheduled",
        generationConfig: weekly([1, 2, 3, 4, 5, 6, 7], "07:50", "07:55"),
    },
    {
        id: "meditar",
        name: "Meditar",
        kind: "habit",
        habitType: "scheduled",
        generationConfig: weekly([1, 2, 3, 4, 5, 6, 7], "08:00", "08:15"),
    },
    {
        id: "hybridge-programacion",
        name: "Hybridge - Programación",
        kind: "activity",
        activityType: "anchor",
        generationConfig: weekly([1, 2, 3, 4, 5], "08:45", "09:45"),
    },
    {
        id: "comida",
        name: "Comida",
        kind: "habit",
        habitType: "scheduled",
        generationConfig: weekly([1, 2, 3, 4, 5, 6, 7], "14:00", "14:30"),
    },
    {
        id: "ccna-estudio",
        name: "CCNA / Estudio",
        kind: "activity",
        activityType: "periodic",
        generationConfig: weekly([1, 3, 5], "19:15", "20:15"),
    },
    {
        id: "preparacion-dia-siguiente",
        name: "Preparación del día siguiente",
        kind: "habit",
        habitType: "scheduled",
        generationConfig: weekly([1, 2, 3, 4, 5, 6, 7], "21:15", "21:45"),
    },
]);
