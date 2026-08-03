// Los datos respetan el contrato temporal y no incluyen información de entregas futuras.
const mockActivities = [
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
        statesByDate: {},
    },
    {
        id: "meditar",
        name: "Meditar",
        position: 3,
        plannedStartTime: "08:00",
        plannedEndTime: "08:15",
        statesByDate: {},
    },
    {
        id: "hybridge-programacion",
        name: "Hybridge - Programación",
        position: 4,
        plannedStartTime: "08:45",
        plannedEndTime: "09:45",
        statesByDate: {},
    },
    {
        id: "comida",
        name: "Comida",
        position: 5,
        plannedStartTime: "14:00",
        plannedEndTime: "14:30",
        statesByDate: {},
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

// Distribuye los cinco estados en la fecha local actual para hacerlos comprobables al abrir la vista.
const demoDate = new Date();
const demoDateKey = [
    demoDate.getFullYear(),
    String(demoDate.getMonth() + 1).padStart(2, "0"),
    String(demoDate.getDate()).padStart(2, "0"),
].join("-");
const demoStatuses = ["pending", "in_progress", "completed", "not_completed", "cancelled"];

demoStatuses.forEach(function assignDemoStatus(status, index) {
    mockActivities[index].statesByDate[demoDateKey] = status;
});
