"""
Software FJ - Sistema integral de gestion de clientes, servicios y reservas.

Proyecto orientado a objetos sin base de datos. Toda la informacion vive en
objetos y listas en memoria; el unico archivo que se escribe es el log de
eventos y errores (software_fj.log).

Conceptos que se aplican:
    - Abstraccion: EntidadBase y Servicio son clases abstractas (ABC).
    - Herencia: Cliente hereda de EntidadBase; las tres clases de servicio
      heredan de Servicio.
    - Polimorfismo: cada servicio sobrescribe calcular_costo_base, describir
      y validar_parametros.
    - Encapsulacion: atributos privados con propiedades y validaciones.
    - Sobrecarga: calcular_costo acepta distintas combinaciones de argumentos
      (Python no tiene sobrecarga nativa, se simula con parametros opcionales
      y singledispatchmethod).
    - Excepciones: personalizadas, try/except/else/finally y encadenamiento
      con "raise ... from ...".
"""

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from functools import singledispatchmethod

# ---------------------------------------------------------------------------
# Configuración del log
# ---------------------------------------------------------------------------
logging.basicConfig(
    filename="software_fj.log",
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("SoftwareFJ")

IVA = 0.19  # impuesto por defecto


# ---------------------------------------------------------------------------
# Excepciones personalizadas
# ---------------------------------------------------------------------------
class ErrorSistema(Exception):
    """Excepcion base de todo el sistema."""


class ClienteInvalidoError(ErrorSistema):
    """Datos del cliente incorrectos o incompletos."""


class ServicioInvalidoError(ErrorSistema):
    """Parametros de un servicio incorrectos."""


class ServicioNoDisponibleError(ErrorSistema):
    """El servicio existe pero no se puede reservar en este momento."""


class ReservaInvalidaError(ErrorSistema):
    """Datos de la reserva incorrectos."""


class OperacionNoPermitidaError(ErrorSistema):
    """Se intento una operacion que el estado actual no permite."""


class CalculoInconsistenteError(ErrorSistema):
    """El calculo de costos produjo un resultado invalido."""


# ---------------------------------------------------------------------------
# Clase abstracta general
# ---------------------------------------------------------------------------
class EntidadBase(ABC):
    """Cualquier cosa con identificador que el sistema pueda describir."""

    # Un contador por tipo de entidad (Cliente, Servicio, Reserva).
    _contadores = {}
    _GRUPO = "Entidad"

    def __init__(self):
        """Asigna el siguiente id de su grupo. Se llama DESPUES de validar,
        asi un objeto invalido no gasta un numero de id."""
        grupo = self._GRUPO
        EntidadBase._contadores[grupo] = EntidadBase._contadores.get(grupo, 0) + 1
        self._id = EntidadBase._contadores[grupo]

    @property
    def id(self):
        return self._id

    @abstractmethod
    def describir(self) -> str:
        """Devuelve una descripcion legible de la entidad."""


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------
class Cliente(EntidadBase):
    """Persona que contrata servicios. Sus datos se validan en las propiedades."""

    _GRUPO = "Cliente"
    _PATRON_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")

    def __init__(self, nombre, documento, email, telefono):
        # Se asigna por las propiedades para que corran las validaciones
        self.nombre = nombre
        self.documento = documento
        self.email = email
        self.telefono = telefono
        super().__init__()  # el id se asigna solo si todo fue válido

    # --- nombre ---
    @property
    def nombre(self):
        return self.__nombre

    @nombre.setter
    def nombre(self, valor):
        if not isinstance(valor, str) or len(valor.strip()) < 3:
            raise ClienteInvalidoError("El nombre debe tener al menos 3 caracteres.")
        if any(c.isdigit() for c in valor):
            raise ClienteInvalidoError("El nombre no puede contener numeros.")
        self.__nombre = valor.strip().title()

    # --- documento ---
    @property
    def documento(self):
        return self.__documento

    @documento.setter
    def documento(self, valor):
        valor = str(valor).strip() if valor is not None else ""
        if not valor.isdigit() or not (6 <= len(valor) <= 12):
            raise ClienteInvalidoError(
                "El documento debe ser numerico y tener entre 6 y 12 digitos."
            )
        self.__documento = valor

    # --- email ---
    @property
    def email(self):
        return self.__email

    @email.setter
    def email(self, valor):
        if not isinstance(valor, str) or not self._PATRON_EMAIL.match(valor.strip()):
            raise ClienteInvalidoError(f"Correo electronico invalido: {valor!r}")
        self.__email = valor.strip().lower()

    # --- teléfono ---
    @property
    def telefono(self):
        return self.__telefono

    @telefono.setter
    def telefono(self, valor):
        valor = str(valor).strip() if valor is not None else ""
        if not valor.isdigit() or len(valor) != 10:
            raise ClienteInvalidoError("El telefono debe tener exactamente 10 digitos.")
        self.__telefono = valor

    def describir(self):
        return (f"Cliente #{self.id}: {self.nombre} | Doc: {self.documento} | "
                f"{self.email} | Tel: {self.telefono}")

    def __str__(self):
        return self.describir()


# ---------------------------------------------------------------------------
# Servicios
# ---------------------------------------------------------------------------
class Servicio(EntidadBase, ABC):
    """Clase abstracta de la que salen todos los servicios de Software FJ."""

    _GRUPO = "Servicio"

    def __init__(self, nombre, tarifa_hora, disponible=True):
        if not isinstance(nombre, str) or not nombre.strip():
            raise ServicioInvalidoError("El servicio necesita un nombre.")
        if not isinstance(tarifa_hora, (int, float)) or isinstance(tarifa_hora, bool) \
                or tarifa_hora <= 0:
            raise ServicioInvalidoError("La tarifa por hora debe ser un numero positivo.")
        self._nombre = nombre.strip()
        self._tarifa_hora = float(tarifa_hora)
        self._disponible = bool(disponible)
        # El id lo asigna la subclase al terminar sus propias validaciones.

    @property
    def nombre(self):
        return self._nombre

    @property
    def tarifa_hora(self):
        return self._tarifa_hora

    @property
    def disponible(self):
        return self._disponible

    @disponible.setter
    def disponible(self, valor):
        self._disponible = bool(valor)

    # --- métodos que cada servicio debe implementar ---
    @abstractmethod
    def calcular_costo_base(self, horas: float) -> float:
        """Costo sin impuestos ni descuentos."""

    @abstractmethod
    def validar_parametros(self, horas: float) -> None:
        """Lanza ServicioInvalidoError si la duracion no es valida."""

    # --- sobrecarga de calcular_costo ---
    # calcular_costo(horas)                  -> con IVA por defecto
    # calcular_costo(horas, impuesto=0.0)    -> con otro impuesto
    # calcular_costo(horas, descuento=0.10)  -> con descuento
    # calcular_costo((horas, impuesto, descuento)) -> con una tupla
    @singledispatchmethod
    def calcular_costo(self, horas, impuesto=IVA, descuento=0.0):
        return self._costo_general(horas, impuesto, descuento)

    @calcular_costo.register(tuple)
    def _(self, datos):
        # Variante que recibe (horas, impuesto, descuento) en una sola tupla
        if len(datos) != 3:
            raise CalculoInconsistenteError("La tupla debe ser (horas, impuesto, descuento).")
        return self._costo_general(*datos)

    def _costo_general(self, horas, impuesto, descuento):
        self.validar_parametros(horas)
        for nombre, valor in (("impuesto", impuesto), ("descuento", descuento)):
            if not isinstance(valor, (int, float)) or isinstance(valor, bool):
                raise CalculoInconsistenteError(
                    f"El {nombre} debe ser un numero (por ejemplo 0.10), no {valor!r}."
                )
        if not 0 <= impuesto <= 1 or not 0 <= descuento < 1:
            raise CalculoInconsistenteError(
                f"Impuesto ({impuesto}) o descuento ({descuento}) fuera de rango."
            )
        total = self.calcular_costo_base(horas) * (1 - descuento) * (1 + impuesto)
        if total <= 0:
            raise CalculoInconsistenteError("El costo calculado no es positivo.")
        return round(total, 2)

    def verificar_disponibilidad(self):
        if not self._disponible:
            raise ServicioNoDisponibleError(f"El servicio '{self.nombre}' no esta disponible.")

    def __str__(self):
        return self.describir()


class ReservaSala(Servicio):
    """Reserva de salas de reuniones. Se cobra por hora mas un recargo por capacidad."""

    def __init__(self, nombre, tarifa_hora, capacidad, disponible=True):
        super().__init__(nombre, tarifa_hora, disponible)
        if not isinstance(capacidad, int) or capacidad <= 0:
            raise ServicioInvalidoError("La capacidad de la sala debe ser un entero positivo.")
        self._capacidad = capacidad
        EntidadBase.__init__(self)  # asigna el id al final

    def validar_parametros(self, horas):
        if not isinstance(horas, (int, float)) or horas <= 0:
            raise ServicioInvalidoError("Las horas deben ser un numero mayor que cero.")
        if horas > 12:
            raise ServicioInvalidoError("Una sala no se puede reservar por mas de 12 horas.")

    def calcular_costo_base(self, horas):
        recargo = 1.15 if self._capacidad > 20 else 1.0
        return self.tarifa_hora * horas * recargo

    def describir(self):
        return (f"Sala '{self.nombre}' (capacidad {self._capacidad}) - "
                f"${self.tarifa_hora:,.0f}/hora")


class AlquilerEquipo(Servicio):
    """Alquiler de equipos. Se cobra por hora y por cantidad de unidades."""

    def __init__(self, nombre, tarifa_hora, unidades=1, disponible=True):
        super().__init__(nombre, tarifa_hora, disponible)
        if not isinstance(unidades, int) or unidades <= 0:
            raise ServicioInvalidoError("Las unidades deben ser un entero positivo.")
        self._unidades = unidades
        EntidadBase.__init__(self)  # asigna el id al final

    def validar_parametros(self, horas):
        if not isinstance(horas, (int, float)) or horas <= 0:
            raise ServicioInvalidoError("Las horas deben ser un numero mayor que cero.")
        if horas > 72:
            raise ServicioInvalidoError("Un equipo no se alquila por mas de 72 horas seguidas.")

    def calcular_costo_base(self, horas):
        return self.tarifa_hora * horas * self._unidades

    def describir(self):
        return (f"Equipo '{self.nombre}' x{self._unidades} - "
                f"${self.tarifa_hora:,.0f}/hora por unidad")


class Asesoria(Servicio):
    """Asesoria especializada. Las asesorias de nivel senior cuestan mas."""

    NIVELES = {"junior": 1.0, "senior": 1.5, "experto": 2.0}

    def __init__(self, nombre, tarifa_hora, nivel="junior", disponible=True):
        super().__init__(nombre, tarifa_hora, disponible)
        if nivel not in self.NIVELES:
            raise ServicioInvalidoError(
                f"Nivel '{nivel}' no valido. Opciones: {', '.join(self.NIVELES)}."
            )
        self._nivel = nivel
        EntidadBase.__init__(self)  # asigna el id al final

    def validar_parametros(self, horas):
        if not isinstance(horas, (int, float)) or horas < 1:
            raise ServicioInvalidoError("Una asesoria dura minimo 1 hora.")
        if horas > 8:
            raise ServicioInvalidoError("Una asesoria no puede superar las 8 horas.")

    def calcular_costo_base(self, horas):
        return self.tarifa_hora * horas * self.NIVELES[self._nivel]

    def describir(self):
        return (f"Asesoria '{self.nombre}' nivel {self._nivel} - "
                f"${self.tarifa_hora:,.0f}/hora")


# ---------------------------------------------------------------------------
# Reserva
# ---------------------------------------------------------------------------
class Reserva(EntidadBase):
    PENDIENTE, CONFIRMADA, CANCELADA, PROCESADA = (
        "PENDIENTE", "CONFIRMADA", "CANCELADA", "PROCESADA"
    )

    _GRUPO = "Reserva"

    def __init__(self, cliente, servicio, horas):
        if not isinstance(cliente, Cliente):
            raise ReservaInvalidaError("La reserva necesita un cliente valido.")
        if not isinstance(servicio, Servicio):
            raise ReservaInvalidaError("La reserva necesita un servicio valido.")
        try:
            servicio.validar_parametros(horas)
        except ServicioInvalidoError as e:
            # Encadenamiento: el error original queda como causa
            raise ReservaInvalidaError(f"Duracion invalida para la reserva: {e}") from e
        self._cliente = cliente
        self._servicio = servicio
        self._horas = horas
        self._estado = self.PENDIENTE
        self._costo = None
        self._fecha = datetime.now()
        super().__init__()  # el id se asigna solo si todo fue válido

    @property
    def estado(self):
        return self._estado

    @property
    def costo(self):
        return self._costo

    def confirmar(self):
        if self._estado != self.PENDIENTE:
            raise OperacionNoPermitidaError(
                f"No se puede confirmar una reserva en estado {self._estado}."
            )
        self._servicio.verificar_disponibilidad()
        self._estado = self.CONFIRMADA
        logger.info("Reserva #%s confirmada.", self.id)

    def cancelar(self):
        if self._estado in (self.CANCELADA, self.PROCESADA):
            raise OperacionNoPermitidaError(
                f"No se puede cancelar una reserva {self._estado}."
            )
        self._estado = self.CANCELADA
        logger.info("Reserva #%s cancelada.", self.id)

    def procesar(self, impuesto=IVA, descuento=0.0):
        """Calcula el costo y deja la reserva como PROCESADA."""
        try:
            if self._estado != self.CONFIRMADA:
                raise OperacionNoPermitidaError(
                    "Solo se procesan reservas confirmadas "
                    f"(estado actual: {self._estado})."
                )
            costo = self._servicio.calcular_costo(self._horas, impuesto, descuento)
        except CalculoInconsistenteError as e:
            raise ReservaInvalidaError("No se pudo procesar la reserva por un error de calculo.") from e
        else:
            # Solo se ejecuta si no hubo excepciones
            self._costo = costo
            self._estado = self.PROCESADA
            logger.info("Reserva #%s procesada. Total: $%s", self.id, f"{costo:,.2f}")
            return costo
        finally:
            logger.info("Intento de procesamiento de la reserva #%s finalizado.", self.id)

    def describir(self):
        costo = f"${self._costo:,.2f}" if self._costo is not None else "sin calcular"
        return (f"Reserva #{self.id} | {self._cliente.nombre} | "
                f"{self._servicio.nombre} | {self._horas}h | {self._estado} | {costo}")

    def __str__(self):
        return self.describir()


# ---------------------------------------------------------------------------
# Gestor: guarda todo en listas y protege el flujo del programa
# ---------------------------------------------------------------------------
class GestorFJ:
    def __init__(self):
        self.clientes = []
        self.servicios = []
        self.reservas = []

    def registrar_cliente(self, *args, **kwargs):
        try:
            cliente = Cliente(*args, **kwargs)
        except TypeError as e:
            # Faltan parámetros: se convierte en un error propio
            raise ClienteInvalidoError(f"Parametros faltantes o sobrantes: {e}") from e
        if any(c.documento == cliente.documento for c in self.clientes):
            raise ClienteInvalidoError(f"Ya existe un cliente con documento {cliente.documento}.")
        self.clientes.append(cliente)
        logger.info("Cliente registrado: #%s %s", cliente.id, cliente.nombre)
        return cliente

    def registrar_servicio(self, clase, *args, **kwargs):
        if not (isinstance(clase, type) and issubclass(clase, Servicio)):
            raise ServicioInvalidoError("El tipo de servicio debe ser una subclase de Servicio.")
        try:
            servicio = clase(*args, **kwargs)
        except TypeError as e:
            raise ServicioInvalidoError(f"Parametros faltantes o sobrantes: {e}") from e
        self.servicios.append(servicio)
        logger.info("Servicio registrado: #%s %s", servicio.id, servicio.nombre)
        return servicio

    def crear_reserva(self, cliente, servicio, horas):
        reserva = Reserva(cliente, servicio, horas)
        self.reservas.append(reserva)
        logger.info("Reserva creada: #%s (%s - %s, %sh)", reserva.id,
                    cliente.nombre, servicio.nombre, horas)
        return reserva


# ---------------------------------------------------------------------------
# Simulación
# ---------------------------------------------------------------------------
def ejecutar(descripcion, funcion):
    """Corre una operacion, la registra en el log y nunca deja caer el programa."""
    print(f"\n>> {descripcion}")
    try:
        resultado = funcion()
    except ErrorSistema as e:
        causa = f" (causa: {e.__cause__})" if e.__cause__ else ""
        logger.error("%s -> %s: %s%s", descripcion, type(e).__name__, e, causa)
        print(f"   [ERROR CONTROLADO] {type(e).__name__}: {e}")
        return None
    except Exception as e:  # cualquier error imprevisto también se contiene
        logger.critical("%s -> error inesperado %s: %s", descripcion, type(e).__name__, e)
        print(f"   [ERROR INESPERADO] {type(e).__name__}: {e}")
        return None
    else:
        logger.info("%s -> OK", descripcion)
        print(f"   [OK] {resultado}")
        return resultado
    finally:
        # Siempre se ejecuta, haya o no error: deja constancia de que la
        # operación terminó y el programa sigue activo.
        logger.info("Fin de la operacion: %s", descripcion)


def main():
    logger.info("=== Inicio de la simulacion de Software FJ ===")
    g = GestorFJ()

    # 1. Cliente válido
    ana = ejecutar("1. Registrar cliente valido (Ana)",
                   lambda: g.registrar_cliente("ana gomez", "1098765432",
                                               "ana@correo.com", "3101234567"))
    # 2. Cliente con correo inválido
    ejecutar("2. Registrar cliente con correo invalido",
             lambda: g.registrar_cliente("Luis Perez", "1012345678", "luis-correo", "3109876543"))
    # 3. Cliente con parámetros faltantes
    ejecutar("3. Registrar cliente con parametros faltantes",
             lambda: g.registrar_cliente("Marta Ruiz", "1055555555"))
    # 4. Segundo cliente válido
    carlos = ejecutar("4. Registrar cliente valido (Carlos)",
                      lambda: g.registrar_cliente("Carlos Diaz", "80123456",
                                                  "carlos@correo.com", "3201112233"))
    # 5. Cliente duplicado
    ejecutar("5. Registrar cliente con documento duplicado",
             lambda: g.registrar_cliente("Ana Gomez", "1098765432",
                                         "otra@correo.com", "3101234567"))

    # 6. Servicios válidos
    sala = ejecutar("6. Crear sala de reuniones",
                    lambda: g.registrar_servicio(ReservaSala, "Sala Andes", 50000, 25))
    equipo = ejecutar("7. Crear alquiler de equipo",
                      lambda: g.registrar_servicio(AlquilerEquipo, "Portatil Pro", 12000, 3))
    asesoria = ejecutar("8. Crear asesoria senior",
                        lambda: g.registrar_servicio(Asesoria, "Arquitectura de software",
                                                     90000, "senior"))
    # 9. Servicio inválido
    ejecutar("9. Crear asesoria con nivel inexistente",
             lambda: g.registrar_servicio(Asesoria, "Consultoria", 70000, "maestro"))
    ejecutar("10. Crear sala con tarifa negativa",
             lambda: g.registrar_servicio(ReservaSala, "Sala Fantasma", -500, 10))

    # Reservas
    r1 = ejecutar("11. Crear reserva valida (Ana - sala, 3h)",
                  lambda: g.crear_reserva(ana, sala, 3))
    ejecutar("12. Confirmar y procesar la reserva de Ana",
             lambda: (r1.confirmar(), r1.procesar())[1])

    ejecutar("13. Crear reserva con duracion invalida (sala, 20h)",
             lambda: g.crear_reserva(ana, sala, 20))
    ejecutar("14. Crear reserva sin cliente",
             lambda: g.crear_reserva(None, sala, 2))

    r2 = ejecutar("15. Crear reserva (Carlos - equipo, 10h)",
                  lambda: g.crear_reserva(carlos, equipo, 10))

    def confirmar_y_procesar_con_descuento():
        r2.confirmar()
        return r2.procesar(impuesto=0.19, descuento=0.10)
    ejecutar("16. Confirmar y procesar con 10% de descuento", confirmar_y_procesar_con_descuento)

    ejecutar("17. Cancelar una reserva ya procesada", lambda: r2.cancelar())

    equipo.disponible = False
    r3 = ejecutar("18. Crear reserva sobre equipo no disponible",
                  lambda: g.crear_reserva(ana, equipo, 5))
    ejecutar("19. Confirmar reserva de servicio no disponible", lambda: r3.confirmar())

    r4 = ejecutar("20. Crear reserva de asesoria (Carlos, 2h)",
                  lambda: g.crear_reserva(carlos, asesoria, 2))
    ejecutar("21. Procesar sin confirmar", lambda: r4.procesar())
    ejecutar("22. Procesar con descuento fuera de rango",
             lambda: (r4.confirmar(), r4.procesar(descuento=1.5))[1])
    ejecutar("23. Cancelar reserva de asesoria", lambda: r4.cancelar())

    # Demostración de la sobrecarga del cálculo de costos
    print("\n>> Variantes de calcular_costo (sobrecarga) sobre la asesoria, 2h")
    variantes = (
        ("solo horas             :", lambda: asesoria.calcular_costo(2)),
        ("horas + sin impuesto   :", lambda: asesoria.calcular_costo(2, impuesto=0.0)),
        ("horas + 20% descuento  :", lambda: asesoria.calcular_costo(2, descuento=0.20)),
        ("tupla (h, imp, desc)   :", lambda: asesoria.calcular_costo((2, 0.19, 0.05))),
        ("descuento como texto   :", lambda: asesoria.calcular_costo(2, descuento="10%")),
    )
    for etiqueta, calculo in variantes:
        try:
            print("  ", etiqueta, calculo())
        except (ErrorSistema, AttributeError) as e:
            logger.error("Variante de calcular_costo fallo: %s", e)
            print("  ", etiqueta, f"[ERROR CONTROLADO] {e}")

    print("\n=== Resumen final ===")
    print(f"Clientes registrados: {len(g.clientes)}")
    for c in g.clientes:
        print("  ", c)
    print(f"Servicios registrados: {len(g.servicios)}")
    for s in g.servicios:
        print("  ", s)
    print(f"Reservas creadas: {len(g.reservas)}")
    for r in g.reservas:
        print("  ", r)

    logger.info("=== Fin de la simulacion: el sistema siguio activo pese a los errores ===")
    print("\nEl programa termino con normalidad. Revisa 'software_fj.log' para ver el detalle.")



if __name__ == "__main__":
    main()
