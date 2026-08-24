import { formatDateKey } from "../utils/date-time.js";

const demoDate = formatDateKey(new Date());

// Es un fixture de bootstrap, no una tercera colección del dominio.
export const mockStatusOverrides = Object.freeze([
    { planItemId: "cepillado-dientes", date: demoDate, status: "in_progress" },
    { planItemId: "meditar", date: demoDate, status: "completed" },
    { planItemId: "preparacion-dia-siguiente", date: demoDate, status: "not_completed" },
    { planItemId: "comida", date: demoDate, status: "cancelled" },
]);
