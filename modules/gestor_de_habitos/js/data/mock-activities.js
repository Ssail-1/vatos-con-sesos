import { formatDateKey } from "../utils/date-time.js";

const demoDateKey = formatDateKey(new Date());

// Esta definición permanece inmutable; el store crea su propia copia para cada carga.
export const initialActivities = [
    {
        id: "gym-pecho",
        name: "Gym - Pecho",
        position: 1,
        plannedStartTime: "05:30",
        plannedEndTime: "07:15",
        statesByDate: {},
    },
    {
        id: "cepillado-dientes",
        name: "Cepillado de dientes",
        position: 2,
        plannedStartTime: "07:50",
        plannedEndTime: "07:55",
        statesByDate: { [demoDateKey]: "in_progress" },
    },
    {
        id: "meditar",
        name: "Meditar",
        position: 3,
        plannedStartTime: "08:00",
        plannedEndTime: "08:15",
        statesByDate: { [demoDateKey]: "completed" },
    },
    {
        id: "hybridge-programacion",
        name: "Hybridge - Programación",
        position: 4,
        plannedStartTime: "08:45",
        plannedEndTime: "09:45",
        statesByDate: { [demoDateKey]: "not_completed" },
    },
    {
        id: "comida",
        name: "Comida",
        position: 5,
        plannedStartTime: "14:00",
        plannedEndTime: "14:30",
        statesByDate: { [demoDateKey]: "cancelled" },
    },
    {
        id: "ccna-estudio",
        name: "CCNA / Estudio",
        position: 6,
        plannedStartTime: "19:15",
        plannedEndTime: "20:15",
        statesByDate: {},
    },
    {
        id: "preparacion-dia-siguiente",
        name: "Preparación del día siguiente",
        position: 7,
        plannedStartTime: "21:15",
        plannedEndTime: "21:45",
        statesByDate: {},
    },
];
