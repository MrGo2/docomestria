"""Golden structure spec for 20465282C_CONTRATO.pdf page 2 (Condiciones económicas + firma).

CaixaBank Payments & Consumer modelo F_AS-5 — page 2 carries the intereses block
(fijo/variable checkboxes, tipo deudor, TAE, demora), coste total y comisiones,
reconocimiento de deuda, domicilio de pago (CAIXABANK), derecho de
desistimiento prose, and the triple firma row (Prestatario / Fiador / Financiador)
with the standard CaixaBank footer + Logalty sidebar noise. Contract from
ZARAGOZA dated 18-11-2022 for 27.177,60 € in 120 plazos de 226,48 €.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/20465282C_CONTRATO.pdf"
PAGE = 2

META = {
    "document_type": "Contrato de Préstamo Financiación Comprador Bienes Muebles (CaixaBank F_AS-5)",
    "annotator": "scaffolder",
    "covers_cases": [
        "caixabank_f_as5_header",
        "intereses_checkbox_fijo_variable",
        "tipo_deudor_tae_demora_inline",
        "coste_total_prestamo_kv",
        "importe_total_adeudado_kv",
        "penalidad_cuota_impagado_kv",
        "comision_cancelacion_anticipada_dual_pct",
        "importe_diario_desistimiento_no_aplica",
        "reconocimiento_deuda_plazos_cuota",
        "domicilio_pago_iban_block",
        "derecho_desistimiento_prose",
        "triple_firma_prestatario_fiador_financiador",
        "firmatag_signature_placeholders",
        "logalty_metadata_sidebar_noise",
        "caixabank_payments_consumer_footer_prose",
    ],
}


STRUCTURE = [
    # ----------------------------------------------------------------
    # Header (modelo + hoja + título + DGRN disclaimer)
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "encabezado",
        "title": "Encabezado modelo",
        "y_hint": 22,
        "children": [
            {
                "type": "kv_leaf",
                "id": "modelo_asnef",
                "label": "Nº Modelo",
                "value": "F_AS-5",
                "y_hint": 22.7,
            },
            {
                "type": "kv_leaf",
                "id": "hoja_numero",
                "label": "Hoja nº",
                "value": "2/25",
                "y_hint": 35.4,
            },
            {
                "type": "kv_leaf",
                "id": "titulo_contrato",
                "label": "Título",
                "value": "CONTRATO DE PRÉSTAMO DE FINANCIACIÓN A COMPRADOR DE BIENES MUEBLES",
                "y_hint": 82.8,
            },
            {
                "type": "prose_block",
                "id": "modelo_dgrn_disclaimer",
                "label": "Modelo aprobado ASNEF/DGRN",
                "text": (
                    "Modelo aprobado a la ASNEF por la Dirección General de los Registros "
                    "y del Notariado (DGRN). (Resolución de 04/02/2000. Modificado por "
                    "Resoluciones de DGRN de 23/05/2006, de 29/09/2011, de 02/07/2013, "
                    "de 23/01/2014, de 07/10/2019, de 07/06/2021 y de 22/09/2022"
                ),
                "y_hint": 95.3,
            },
        ],
    },

    # ----------------------------------------------------------------
    # Intereses block — checkboxes + tipo deudor + TAE + demora
    # Atoms show a tangled multi-column row at y≈147..170.
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "intereses",
        "title": "Intereses",
        "y_hint": 147.0,
        "children": [
            {
                "type": "kv_group",
                "id": "intereses_modalidad",
                "pairs": [
                    {
                        "label": "Intereses por: Fijo",
                        "value": "X",
                        "y_hint": 147.0,
                        "x_hint": 27.0,
                    },
                    {
                        "label": "Intereses por: Variable",
                        "value": "",
                        "y_hint": 162.8,
                        "x_hint": 99.3,
                    },
                    {
                        "label": "Aplazamiento: Variable",
                        "value": "",
                        "y_hint": 163.7,
                        "x_hint": 27.0,
                    },
                ],
            },
            {
                "type": "kv_group",
                "id": "intereses_tipos",
                "pairs": [
                    {
                        "label": "Tipo deudor",
                        "value": "5,99% anual",
                        "y_hint": 162.8,
                        "x_hint": 203.3,
                    },
                    {
                        "label": "TAE / TAE Variable (Condición General 8ª)",
                        "value": "7,07%",
                        "y_hint": 166.2,
                        "x_hint": 349.6,
                    },
                    {
                        "label": "Intereses de demora",
                        "value": "7,990% anual / 6.768,85",
                        "y_hint": 163.9,
                        "x_hint": 444.6,
                    },
                ],
            },
        ],
    },

    # ----------------------------------------------------------------
    # Coste / Importe total / Penalidad / Comisión cancelación
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "condiciones_economicas",
        "title": "Condiciones económicas",
        "y_hint": 193.5,
        "children": [
            {
                "type": "kv_leaf",
                "id": "coste_total_prestamo",
                "label": "Coste total del Préstamo para el prestatario",
                "value": "7.544,36",
                "y_hint": 193.5,
            },
            {
                "type": "prose_block",
                "id": "coste_total_desglose_label",
                "label": "Detalle conceptos coste total",
                "text": (
                    "(gastos, intereses, comisiones, impuestos, "
                    "Servicios accesorios condicionantes, etc.)"
                ),
                "y_hint": 210.4,
            },
            {
                "type": "kv_leaf",
                "id": "importe_total_adeudado",
                "label": "Importe Total adeudado por el prestatario",
                "value": "27.177,60",
                "y_hint": 230.5,
            },
            {
                "type": "prose_block",
                "id": "espacio_comisiones_eventuales",
                "label": "Espacio reservado comisiones eventuales",
                "text": "Espacio reservado para incluir comisiones eventuales y futuras.",
                "y_hint": 247.4,
            },
            {
                "type": "kv_leaf",
                "id": "penalidad_cuota_impagado",
                "label": "Penalidad por cada cuota impagado",
                "value": "35 (se cobrará una sola vez para cada cuota)",
                "y_hint": 261.0,
            },
            {
                "type": "kv_group",
                "id": "comision_cancelacion_anticipada",
                "pairs": [
                    {
                        "label": "Comisión por cancelación anticipada",
                        "value": "1,00 % de la deuda cancelada",
                        "y_hint": 274.6,
                        "x_hint": 213.2,
                    },
                    {
                        "label": "Comisión cancelación anticipada (< 1 año)",
                        "value": "0,500 % si para la terminación del contrato queda menos de un año",
                        "y_hint": 274.6,
                        "x_hint": 367.4,
                    },
                ],
            },
            {
                "type": "kv_leaf",
                "id": "importe_diario_desistimiento",
                "label": "Importe diario derecho de desistimiento",
                "value": "NO APLICA",
                "y_hint": 316.5,
            },
        ],
    },

    # ----------------------------------------------------------------
    # Reconocimiento de deuda
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "reconocimiento_deuda",
        "title": "RECONOCIMIENTO DE DEUDA",
        "y_hint": 333.8,
        "children": [
            {
                "type": "kv_leaf",
                "id": "reconocimiento_importe",
                "label": "Importe reconocido a favor del financiador",
                "value": "27.177,60",
                "y_hint": 333.8,
            },
            {
                "type": "kv_leaf",
                "id": "reconocimiento_n_plazos",
                "label": "Nº de plazos",
                "value": "120",
                "y_hint": 348.4,
            },
            {
                "type": "kv_leaf",
                "id": "reconocimiento_cuota",
                "label": "Importe de cada plazo",
                "value": "226,48",
                "y_hint": 349.5,
            },
            {
                "type": "prose_block",
                "id": "reconocimiento_vencimientos",
                "label": "Vencimientos según cuadro de amortización",
                "text": (
                    "cada uno, con los vencimientos que se detallan en el "
                    "cuadro de amortización."
                ),
                "y_hint": 350.7,
            },
        ],
    },

    # ----------------------------------------------------------------
    # Domicilio de pago
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "domicilio_pago",
        "title": "DOMICILIO DE PAGO",
        "y_hint": 381.4,
        "children": [
            {
                "type": "kv_group",
                "id": "domicilio_pago_datos",
                "pairs": [
                    {
                        "label": "Entidad",
                        "value": "CAIXABANK, S.A.",
                        "y_hint": 381.4,
                    },
                    {
                        "label": "Domicilio",
                        "value": "C. GARAY, 3",
                        "y_hint": 382.6,
                        "x_hint": 309.9,
                    },
                    {
                        "label": "Localidad",
                        "value": "LA ALMUNIA - ZARAGOZA",
                        "y_hint": 397.4,
                    },
                    {
                        "label": "Nº de cuenta",
                        "value": "ES23 2100 4354 9101 0044 9454",
                        "y_hint": 398.5,
                        "x_hint": 324.9,
                    },
                ],
            },
            {
                "type": "prose_block",
                "id": "autorizacion_cobro",
                "label": "Autorización de cobro",
                "text": (
                    "A estos efectos el Prestatario autoriza expresamente al financiador "
                    "a presentar al cobro en la cuenta las cantidades exactas resultantes "
                    "del presente contrato."
                ),
                "y_hint": 414.5,
            },
        ],
    },

    # ----------------------------------------------------------------
    # Derecho de desistimiento + Duración del contrato (prose)
    # ----------------------------------------------------------------
    {
        "type": "prose_block",
        "id": "derecho_desistimiento",
        "label": "Derecho de desistimiento",
        "text": (
            "Derecho de desistimiento. (Art. 9.4 de la Ley de Venta a Plazos de Bienes "
            "Muebles y art. 28 de la Ley de Crédito al Consumo según Condición General 13)."
        ),
        "y_hint": 456.8,
    },
    {
        "type": "prose_block",
        "id": "duracion_contrato",
        "label": "Duración del contrato",
        "text": "Duración del contrato – (ver anexo I) Cuadro de amortización del contrato",
        "y_hint": 482.2,
    },
    {
        "type": "prose_block",
        "id": "info_previa_consumidores",
        "label": "Información previa al contrato",
        "text": (
            "Los intervinientes, caso de ser consumidores a los efectos de la Ley de "
            "Contratos de crédito al consumo, declaran haber recibido la información "
            "previa al contrato y la explicación personalizada, con la debida antelación "
            "y en los términos exigidos en la misma."
        ),
        "y_hint": 494.7,
    },
    {
        "type": "prose_block",
        "id": "aceptacion_condiciones",
        "label": "Aceptación de condiciones particulares y generales",
        "text": (
            "Los abajo firmantes conocen y aceptan el contenido de las Condiciones "
            "Particulares y Generales del presente contrato del que declaran haber "
            "recibido la correspondiente copia."
        ),
        "y_hint": 532.8,
    },
    {
        "type": "prose_block",
        "id": "ejemplares_hojas",
        "label": "Ejemplares y hojas",
        "text": (
            "En prueba de conformidad, firman las partes el presente contrato en 25 "
            "hojas y en 1 ejemplar/es"
        ),
        "y_hint": 558.0,
    },

    # ----------------------------------------------------------------
    # Triple firma row (Prestatario / Fiador / Financiador)
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "firmas",
        "title": "Firmas de las partes",
        "y_hint": 576.2,
        "children": [
            {
                "type": "kv_group",
                "id": "firma_lugar_fecha",
                "pairs": [
                    {
                        "label": "En (Prestatario)",
                        "value": "ZARAGOZA",
                        "y_hint": 576.2,
                        "x_hint": 27.0,
                    },
                    {
                        "label": "En (Fiador)",
                        "value": "ZARAGOZA",
                        "y_hint": 576.2,
                        "x_hint": 280.7,
                    },
                    {
                        "label": "En (Financiador)",
                        "value": "ZARAGOZA",
                        "y_hint": 576.2,
                        "x_hint": 409.0,
                    },
                    {
                        "label": "Fecha (Prestatario)",
                        "value": "18-11-2022",
                        "y_hint": 595.7,
                        "x_hint": 27.0,
                    },
                    {
                        "label": "Fecha (Fiador)",
                        "value": "18-11-2022",
                        "y_hint": 595.7,
                        "x_hint": 280.7,
                    },
                    {
                        "label": "Fecha (Financiador)",
                        "value": "18-11-2022",
                        "y_hint": 595.7,
                        "x_hint": 409.0,
                    },
                ],
            },
            {
                "type": "signature_placeholder",
                "id": "firma_prestatario_label",
                "label": "Prestatario/s",
                "value": "",
                "y_hint": 615.1,
            },
            {
                "type": "signature_placeholder",
                "id": "firma_fiador_label",
                "label": "Fiador/es",
                "value": "",
                "y_hint": 615.1,
            },
            {
                "type": "signature_placeholder",
                "id": "firma_financiador_label",
                "label": "Financiador",
                "value": "",
                "y_hint": 615.1,
            },
        ],
    },

    # ----------------------------------------------------------------
    # Footnote + footer prose (financiador legal + REVERSO disclaimer)
    # ----------------------------------------------------------------
    {
        "type": "prose_block",
        "id": "anexo_ii_footnote",
        "label": "Notas a pie (anexos)",
        "text": (
            "(1) Si son varios deberá utilizarse anexo II, "
            "(2) Si son varios deberá utilizarse anexo II, (3) Si s"
        ),
        "y_hint": 734.1,
    },
    {
        "type": "prose_block",
        "id": "datos_financiador_footer",
        "label": "Datos del financiador (pie)",
        "text": (
            "Datos del financiador: CaixaBank Payments & Consumer, E.F.C., E.P., S.A.U., "
            "domiciliada en Avenida de Manoteras nº 20. E Madrid, CIF A-08980153. "
            "Inscrita en el Registro Mercantil de Madrid, Tomo 36.556, Folio 29, "
            "Hoja M-6 Establecimientos de Crédito del Banco de España."
        ),
        "y_hint": 752.1,
    },
    {
        "type": "prose_block",
        "id": "reverso_disclaimer",
        "label": "Reverso disclaimer",
        "text": (
            "REVERSO SÓLO APTO PARA LA IMPRESIÓN DE LAS CONDICIONES PARTICULARES "
            "CONTENIDAS EN EL B. O. E., SEGÚN"
        ),
        "y_hint": 792.6,
    },

    # ----------------------------------------------------------------
    # Logalty sidebar noise + footer mod code + signature tags
    # ----------------------------------------------------------------
    {
        "type": "noise",
        "id": "sidebar_paginacion",
        "text": "2/34",
        "kind": "page_number",
        "y_hint": 274.3,
    },
    {
        "type": "noise",
        "id": "sidebar_pages_label",
        "text": "Pages:",
        "kind": "logalty_metadata",
        "y_hint": 298.3,
    },
    {
        "type": "noise",
        "id": "sidebar_tz",
        "text": "+0100 -",
        "kind": "logalty_metadata",
        "y_hint": 341.5,
    },
    {
        "type": "noise",
        "id": "sidebar_tz_name",
        "text": "CET",
        "kind": "logalty_metadata",
        "y_hint": 370.3,
    },
    {
        "type": "noise",
        "id": "sidebar_hora",
        "text": "18:36:10",
        "kind": "logalty_metadata",
        "y_hint": 389.5,
    },
    {
        "type": "noise",
        "id": "sidebar_fecha_t",
        "text": "2022/11/18 T",
        "kind": "logalty_metadata",
        "y_hint": 442.3,
    },
    {
        "type": "noise",
        "id": "sidebar_date",
        "text": "Date:",
        "kind": "logalty_metadata",
        "y_hint": 495.1,
    },
    {
        "type": "noise",
        "id": "sidebar_guid_par",
        "text": "001001-0001-000000080792820.par -",
        "kind": "logalty_metadata",
        "y_hint": 533.5,
    },
    {
        "type": "noise",
        "id": "sidebar_guid",
        "text": "Guid:",
        "kind": "logalty_metadata",
        "y_hint": 687.1,
    },
    {
        "type": "noise",
        "id": "sidebar_logalty",
        "text": "Logalty",
        "kind": "logalty_metadata",
        "y_hint": 715.9,
    },
    {
        "type": "noise",
        "id": "firmatag_prestatario",
        "text": "@$FIRMATAG{<signature><id>1</id><width>44</width><height>7</height><nif>20465282C</nif></signature>}",
        "kind": "watermark",
        "y_hint": 658.1,
    },
    {
        "type": "noise",
        "id": "firmatag_financiador",
        "text": "a@$FIRMATAG{<signature><id>6</id><width>44</width><height>7</height><nif></nif></signature>}$@",
        "kind": "watermark",
        "y_hint": 658.1,
    },
    {
        "type": "noise",
        "id": "footer_mod_code",
        "text": "MOD. (M)006-720.0313-02 (24) - 10 de octubre de 2022",
        "kind": "page_number",
        "y_hint": 789.1,
    },
]
