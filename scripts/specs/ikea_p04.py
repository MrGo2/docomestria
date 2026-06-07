"""Golden structure spec for CONTRATO IKEA.pdf page 4 (DATOS ECONÓMICOS).

Two tables:
- Datos base: simple 2-col (label/value) — Número, Fecha, Límite
- Tipos de Interés: 3-col table (label / En Establecimiento IKEA / Fuera de IKEA)
  with some rows having only the IKEA column (merged across both visual columns)
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO IKEA.pdf"
PAGE = 4

META = {
    "document_type": "Contrato de cuenta de crédito con o sin Tarjeta IKEA (CaixaBank Payments & Consumer)",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_ikea_datos_economicos_base",
        "caixabank_ikea_tipos_interes_multi_column",
        "caixabank_ikea_merged_full_width_cells",
        "caixabank_ikea_forma_pago_long_multi_paragraph",
        "caixabank_ikea_empty_cuota_initial",
    ],
}


_FORMA_PAGO = (
    "Si usted ha elegido la modalidad de pago Fin de Mes, realizará el pago total del crédito "
    "dispuesto durante el mes, sin intereses, a final de mes. A este importe se le sumará el "
    "precio correspondiente al resto de los servicios que le hayamos prestado durante el periodo "
    "(comisión o precio por algún servicio que pudiera haber realizado, como por ejemplo, la "
    "comisión por retirada de dinero en efectivo en un cajero o la prima del seguro en caso de "
    "ser contratado, entre otras). "
    "Si usted ha elegido la modalidad de Pago Aplazado (Revolving), realizará el pago del crédito "
    "mediante una cuota mensual del importe que usted elija, que incluye capital (parte del "
    "crédito total que haya dispuesto ese mes así como anteriores) + intereses + prima del seguro "
    "(en caso de ser contratado). "
    "Si usted ha elegido la modalidad de Pago Fraccionado, realizará el pago del crédito mediante "
    "una cuota mensual en los plazos que acordemos, que incluye la cuota correspondiente al "
    "fraccionamiento de la operación solicitada por usted y el importe total de la cuota que haya "
    "elegido pagar por el resto del crédito usado + intereses + prima de seguro (en caso de "
    "tenerlo contratado). "
    "En la modalidad de Pago Aplazado (Revolving)y de Pago Fraccionado, a la cuota se le sumará "
    "el precio correspondiente al resto de los servicios que le hayamos prestado durante el "
    "periodo (comisión por algún servicio que pudiera haber realizado, como por ejemplo, la "
    "comisión por retirada de dinero en efectivo en un cajero, entre otras (excepto la prima del "
    "seguro, en caso de ser contratado, que ya se habría incluido en la cuota))."
)

_TIN_FRAC_FIN_MES = (
    "TIN 14,95% anual (TAE 16,02%) cuando se fraccione el importe a partir de 6 meses, inclusive. "
    "Cuando se fraccione el importe de las compras en 3 meses, el tipo de interés será 0%, "
    "aplicándose el coste indicado en el apartado \"Precio de los Servicios\" (TAE 19,77%)."
)

_CUOTA_MINIMA = (
    "Usted podrá escoger qué cuota quiere pagar mensualmente, siempre a partir de una cuota "
    "mínima que nosotros fijamos aplicando una fórmula que evita que tenga que pagar lo que vaya "
    "gastando durante un período de tiempo muy prolongado. Se lo explicamos a continuación."
)


STRUCTURE = [
    {
        "type": "section",
        "id": "datos_economicos",
        "title": "DATOS ECONÓMICOS",
        "y_hint": 83,
        "children": [
            {
                "type": "table",
                "id": "datos_base",
                "title": "Datos base del contrato",
                "y_hint": 127,
                "columns": [
                    {"id": "label", "label": "Concepto", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {
                        "label": ("Número de contrato:", 127),
                        "value": ("202502270270913", 127),
                    },
                    {
                        "label": ("Fecha de firma:", 154),
                        "value": ("25 de Febrero de 2025", 154),
                    },
                    {
                        "label": ("Límite de Crédito:", 176),
                        "value": ("1.800,00 euros", 176),
                    },
                ],
            },
            {
                "type": "table",
                "id": "tipos_interes",
                "title": "Tipos de Interés",
                "y_hint": 198,
                "columns": [
                    {"id": "label", "label": "Concepto", "type": "text"},
                    {"id": "en_ikea", "label": "En Establecimiento IKEA", "type": "text"},
                    {"id": "fuera_ikea", "label": "Fuera de IKEA", "type": "text"},
                ],
                "rows": [
                    {
                        "label": (
                            "Tipo de interés en las compras realizadas con modalidad de Pago Fraccionado.",
                            217,
                        ),
                        "en_ikea": (
                            "TIN 9,95% anual (TAE 10,43%). En determinadas compras podrá ofrecerse "
                            "un TIN inferior, incluso a 0%.",
                            217,
                        ),
                        "fuera_ikea": ("Operativa no permitida.", 217),
                    },
                    {
                        "label": (
                            "Tipo de interés del Pago Fraccionado de las compras realizadas "
                            "inicialmente bajo la modalidad de Pago Fin de Mes.",
                            284,
                        ),
                        "en_ikea": (_TIN_FRAC_FIN_MES, 284),
                    },
                    {
                        "label": (
                            "Tipo de interés en las compras realizadas con modalidad de Pago "
                            "Aplazado (Revolving).",
                            343,
                        ),
                        "en_ikea": ("TIN 9,95% anual (TAE 10,42%).", 343),
                        "fuera_ikea": ("TIN 20,88% anual (TAE 23%).", 343),
                    },
                    {
                        "label": ("Tipo de interés por demora:", 391),
                        "en_ikea": (
                            "Tipo de interés aplicado a cada disposición/operación impagada más "
                            "dos puntos porcentuales.",
                            387,
                        ),
                    },
                    {
                        "label": ("Forma de pago:", 473),
                        "en_ikea": (_FORMA_PAGO, 416),
                    },
                    {
                        "label": (
                            "Cuota mensual elegida inicialmente para la modalidad de Pago "
                            "Aplazado (Revolving):",
                            723,
                        ),
                        "en_ikea": ("", 723),
                    },
                    {
                        "label": ("Cuota mínima para Pago Aplazado (Revolving):", 754),
                        "en_ikea": (_CUOTA_MINIMA, 751),
                    },
                ],
            },
        ],
    },
]
