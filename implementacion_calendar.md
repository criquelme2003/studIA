Guía de integración — Chat unificado studIA
Endpoint

POST https://presenciasur.com/studia/api/chat/deepseek
Authorization: Bearer <access_token>
Content-Type: application/json
Request

{
  prompt: string,                // mensaje del usuario — siempre requerido
  current_date?: string,         // ISO 8601 — "2026-03-28T10:00:00" — mandar siempre
  subject_id?: string,           // UUID — solo si el usuario filtra por asignatura
  events?: CalendarEvent[]       // ver abajo — mandar siempre que el chat esté abierto
}

type CalendarEvent = {
  id: string,        // ID de Expo Calendar — requerido para editar/eliminar
  title: string,
  start: string,     // ISO 8601
  end: string,       // ISO 8601
  location?: string,
  notes?: string,
}
¿Qué eventos mandar? Cargar con Calendar.getEventsAsync() una ventana de ±30 días desde hoy cada vez que el usuario abre el chat. No hace falta recargar en cada mensaje.

Response

{
  reply: string,                  // SIEMPRE presente — texto para mostrar en el chat bubble

  // Calendario
  action: "ai_reply" | "create" | "update" | "delete",
  event?: {                       // presente en create y update
    title: string,
    start: string,                // ISO 8601
    end: string,                  // ISO 8601
    location?: string,
    notes?: string,
  },
  event_id?: string,              // presente en update y delete — es el id de Expo Calendar

  // Estudio
  sources?: { file_id, filename, subject_name }[],   // archivos usados como contexto
  suggested_subject?: { id, name },                  // asignatura sugerida por el agente
}
Lógica de control por action

const res = await fetch('/chat/deepseek', { ... })
const data = await res.json()

// 1. Siempre mostrar el reply en el chat
appendMessage({ role: 'assistant', text: data.reply })

// 2. Ejecutar acción de calendario si corresponde
switch (data.action) {
  case 'create':
    const newId = await Calendar.createEventAsync(calendarId, {
      title: data.event.title,
      startDate: new Date(data.event.start),
      endDate: new Date(data.event.end),
      location: data.event.location,
      notes: data.event.notes,
    })
    // opcional: guardar newId si querés permitir edición posterior en la misma sesión
    break

  case 'update':
    await Calendar.updateEventAsync(data.event_id, {
      title: data.event.title,
      startDate: new Date(data.event.start),
      endDate: new Date(data.event.end),
      location: data.event.location,
      notes: data.event.notes,
    })
    break

  case 'delete':
    await Calendar.deleteEventAsync(data.event_id)
    break

  case 'ai_reply':
    // nada extra — solo el reply ya mostrado
    break
}

// 3. Si hay suggested_subject, mostrar chip de confirmación
if (data.suggested_subject) {
  showSubjectConfirmation(data.suggested_subject)
  // al confirmar → PATCH /files/{file_id}/subject con { subject_id }
}

// 4. Si hay sources, mostrar referencias debajo del bubble
if (data.sources?.length) {
  appendSources(data.sources)
}
Casos edge a manejar en el front
Caso	Qué hacer
action: "update" pero event_id no existe en el calendario local	Mostrar error amigable: "No encontré el evento para editarlo"
action: "create" y el usuario no dio permiso de calendario	Pedir permiso con Calendar.requestCalendarPermissionsAsync() antes del primer request
La API responde 502	Mostrar "No pude conectarme al asistente, intenta de nuevo"
reply vacío (no debería pasar pero por las dudas)	Mostrar "..." como fallback
Permisos Expo Calendar
Pedir una sola vez al iniciar la app o al abrir el chat por primera vez:


const { status } = await Calendar.requestCalendarPermissionsAsync()
if (status !== 'granted') {
  // deshabilitar funcionalidad de calendario en el chat
}
En iOS también se necesita requestRemindersPermissionsAsync() si van a usar recordatorios.

Notas
current_date es crítico — sin él el agente no sabe qué es "mañana" o "el jueves".
Los eventos se mandan en cada request para que el agente pueda editar/eliminar por nombre. Si el usuario tiene muchos eventos, acotar la ventana a ±15 días.
El campo notes de event puede venir como "" — tratarlo igual que undefined al llamar a Expo Calendar.