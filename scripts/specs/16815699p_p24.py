"""Golden structure spec for 16815699P_CONTRATO.pdf page 24 (ANEXO IV - Otros Pactos, hoja final).

CaixaBank Payments & Consumer modelo F_AS-5 - last page (24/24). Contains ANEXO IV
OTROS PACTOS with sections A.14 DURACIÓN, A.15 PROCEDIMIENTO EXTRAJUDICIAL DE
RECLAMACIÓN (with SAC / Banco de España contact KVs embedded in prose), A.16
CONDICIÓN SUSPENSIVA Y MOTIVO ADICIONAL DE RESOLUCIÓN, and signature row
(Prestatario/s | Fiador/es | Financiador) at the bottom.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/16815699P_CONTRATO.pdf"
PAGE = 24

META = {
    "document_type": "Contrato de Préstamo Financiación Comprador Bienes Muebles (CaixaBank F_AS-5)",
    "annotator": "scaffolder",
    "covers_cases": [
        "caixabank_f_as5_header_final_page",
        "anexo_iv_otros_pactos_title",
        "anexo_reference_impreso_titular",
        "section_a14_duracion_prose",
        "section_a15_procedimiento_extrajudicial_with_inline_kvs",
        "sac_contact_postal_web_email",
        "banco_de_espana_supervision_domicilio_web",
        "telefono_atencion_cliente_gratuito",
        "section_a16_condicion_suspensiva_clauses_a_b",
        "signature_row_three_placeholders",
        "logalty_sidebar_metadata_noise",
        "reverso_no_apto_impresion_footer",
    ],
}


STRUCTURE = [
    # ----------------------------------------------------------------
    # Header (modelo + hoja)
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
                "y_hint": 22,
            },
            {
                "type": "kv_leaf",
                "id": "hoja_numero",
                "label": "Hoja nº",
                "value": "24/24",
                "y_hint": 47,
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
                "y_hint": 78,
            },
        ],
    },

    # ----------------------------------------------------------------
    # ANEXO IV / OTROS PACTOS title + reference line
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "anexo_iv_otros_pactos",
        "title": "ANEXO IV - OTROS PACTOS",
        "y_hint": 129,
        "children": [
            {
                "type": "kv_leaf",
                "id": "anexo_impreso_numero",
                "label": "Impreso nº",
                "value": "6249596",
                "y_hint": 159,
            },
            {
                "type": "kv_leaf",
                "id": "anexo_titular_nombre",
                "label": "Titular",
                "value": "LUIS FERNANDO JUSTINIANO JUSTINIANO",
                "y_hint": 172,
            },
        ],
    },

    # ----------------------------------------------------------------
    # A.14 DURACIÓN (prose only, no KVs)
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "a14_duracion",
        "title": "A.14.- DURACIÓN",
        "y_hint": 200,
        "children": [
            {
                "type": "prose_block",
                "id": "a14_duracion_prose",
                "label": "A.14 Duración - texto",
                "text": (
                    "El presente contrato tiene una duración especificada en las Condiciones "
                    "Particulares al referirse a los vencimientos y c anticipada supondrá "
                    "también la finalización de este contrato."
                ),
                "y_hint": 213,
            },
        ],
    },

    # ----------------------------------------------------------------
    # A.15 PROCEDIMIENTO EXTRAJUDICIAL DE RECLAMACIÓN Y RECURSO PARA EL TITULAR
    # Long prose with embedded KVs (SAC postal / web / email, BdE domicilio + web, teléfono).
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "a15_procedimiento_extrajudicial",
        "title": "A.15.- PROCEDIMIENTO EXTRAJUDICIAL DE RECLAMACIÓN Y RECURSO PARA EL TITULAR",
        "y_hint": 251,
        "children": [
            {
                "type": "prose_block",
                "id": "a15_intro_sac",
                "label": "A.15 Intro SAC",
                "text": (
                    "CaixaBank Payments & Consumerque no está adherida a la junta arbitral "
                    "de consumo, tiene establecido un Servicio de Atención al Cliente (SAC), "
                    "de conformidad con lo previsto al efecto en la normativa vigente, a "
                    "quien podrán dirigirse las reclamaciones y quejas:"
                ),
                "y_hint": 263,
            },
            {
                "type": "kv_leaf",
                "id": "sac_domicilio_postal",
                "label": "SAC - Correo postal",
                "value": "calle Pintor Sorolla, 2-4, 46002, Valencia",
                "y_hint": 289,
            },
            {
                "type": "kv_leaf",
                "id": "sac_web_formulario",
                "label": "SAC - Formulario web",
                "value": "http://www.caixabankpc.com",
                "y_hint": 315,
            },
            {
                "type": "kv_leaf",
                "id": "sac_email",
                "label": "SAC - Correo electrónico",
                "value": "servicio.cliente@caixabank.com",
                "y_hint": 328,
            },
            {
                "type": "prose_block",
                "id": "a15_otros_canales",
                "label": "A.15 Otros canales SAC",
                "text": (
                    "· mediante escrito entregado en cualquiera de las oficinas de "
                    "CaixaBank, S.A. · o aquel otro que en el futuro se comunique "
                    "debidamente a tal fin."
                ),
                "y_hint": 340,
            },
            {
                "type": "prose_block",
                "id": "a15_recurso_comisionados",
                "label": "A.15 Recurso a Comisionados",
                "text": (
                    "Si transcurren los plazos que indique la normativa de aplicación desde "
                    "la presentación del escrito de reclamación o queja sin obtener "
                    "resolución o en caso de disconformidad con la resolución del SAC, el "
                    "reclamante podrá dirigirse a cualquiera de los Comisionados por la "
                    "Defensa del Cliente de Servicios Financieros –o aquella otra instancia "
                    "que, en su caso, llegado el momento, reglamentariamente sustituya a "
                    "éstos-, siendo imprescindible haber presentado previamente la "
                    "reclamación ante el Servicio de Atención al Cliente de CaixaBank "
                    "Payments & Consumer."
                ),
                "y_hint": 365,
            },
            {
                "type": "kv_leaf",
                "id": "banco_espana_domicilio",
                "label": "Banco de España - Domicilio",
                "value": "Madrid, calle Alcalá, 50",
                "y_hint": 417,
            },
            {
                "type": "kv_leaf",
                "id": "banco_espana_web",
                "label": "Banco de España - Página web",
                "value": "www.bde.es",
                "y_hint": 430,
            },
            {
                "type": "kv_leaf",
                "id": "telefono_atencion_cliente",
                "label": "Teléfono atención al cliente",
                "value": "900 101 601",
                "y_hint": 442,
            },
        ],
    },

    # ----------------------------------------------------------------
    # A.16 CONDICIÓN SUSPENSIVA Y MOTIVO ADICIONAL DE RESOLUCIÓN (prose, clauses a/b)
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "a16_condicion_suspensiva_resolucion",
        "title": "A.16.- CONDICIÓN SUSPENSIVA Y MOTIVO ADICIONAL DE RESOLUCIÓN DEL PRESENTE CONTRATO",
        "y_hint": 481,
        "children": [
            {
                "type": "prose_block",
                "id": "a16_a_condicion_suspensiva",
                "label": "a) Condición suspensiva",
                "text": (
                    "a) Condición suspensiva para la validezy eficacia del presente "
                    "contrato. Este contrato será válido y eficaz y, por tanto, surtirán "
                    "efectos jurídicos del mismo, a partir del momento en que el Fi "
                    "información y/o documentación del prestatario que este considere "
                    "necesaria y se le requiera en relación a sus datos pers "
                    "socio-económicos."
                ),
                "y_hint": 493,
            },
            {
                "type": "prose_block",
                "id": "a16_b_causa_resolucion",
                "label": "b) Causa de resolución",
                "text": (
                    "b) Causa de resolución de este contrato. Sin perjuicio de lo estipulado "
                    "en las restantes condiciones de este contrato y en la Ley, el "
                    "Financiador podrá dar por r supuesto de que los datos personales, "
                    "identificativos y/o socio-económicos facilitados por el prestatario, "
                    "que constituy de esta financiación, no fueran veraces. En este caso, "
                    "el prestatario quedará obligado a la reintegración de la totalida "
                    "carácter inmediato a la comunicación de la resolución del presente "
                    "contrato."
                ),
                "y_hint": 544,
            },
        ],
    },

    # ----------------------------------------------------------------
    # Signature row at bottom (3 empty placeholders)
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "firmas",
        "title": "Firmas",
        "y_hint": 724,
        "children": [
            {
                "type": "signature_placeholder",
                "id": "firma_prestatario",
                "label": "Prestatario/s",
                "value": "",
                "y_hint": 724,
            },
            {
                "type": "signature_placeholder",
                "id": "firma_fiador",
                "label": "Fiador/es",
                "value": "",
                "y_hint": 724,
            },
            {
                "type": "signature_placeholder",
                "id": "firma_financiador",
                "label": "Financiador",
                "value": "",
                "y_hint": 724,
            },
        ],
    },

    # ----------------------------------------------------------------
    # Sidebar Logalty metadata (vertical text at right edge)
    # ----------------------------------------------------------------
    {
        "type": "noise",
        "id": "logalty_pages_marker",
        "text": "24/29",
        "kind": "logalty_metadata",
        "y_hint": 269,
    },
    {
        "type": "noise",
        "id": "logalty_pages_label",
        "text": "- Pages:",
        "kind": "logalty_metadata",
        "y_hint": 331,
    },
    {
        "type": "noise",
        "id": "logalty_tz_offset",
        "text": "+0200",
        "kind": "logalty_metadata",
        "y_hint": 341,
    },
    {
        "type": "noise",
        "id": "logalty_tz_name",
        "text": "CEST",
        "kind": "logalty_metadata",
        "y_hint": 370,
    },
    {
        "type": "noise",
        "id": "logalty_time",
        "text": "20:05:47",
        "kind": "logalty_metadata",
        "y_hint": 394,
    },
    {
        "type": "noise",
        "id": "logalty_date",
        "text": "2024/05/09 T",
        "kind": "logalty_metadata",
        "y_hint": 447,
    },
    {
        "type": "noise",
        "id": "logalty_date_label",
        "text": "Date:",
        "kind": "logalty_metadata",
        "y_hint": 499,
    },
    {
        "type": "noise",
        "id": "logalty_dash",
        "text": "-",
        "kind": "logalty_metadata",
        "y_hint": 528,
    },
    {
        "type": "noise",
        "id": "logalty_guid",
        "text": "Guid: 001001-0001-000000124609130.par",
        "kind": "logalty_metadata",
        "y_hint": 691,
    },
    {
        "type": "noise",
        "id": "logalty_name",
        "text": "Logalty",
        "kind": "logalty_metadata",
        "y_hint": 720,
    },

    # ----------------------------------------------------------------
    # Footer
    # ----------------------------------------------------------------
    {
        "type": "noise",
        "id": "footer_reverso_no_apto",
        "text": "REVERSO NO APTO PARA SU IMPRESIÓN",
        "kind": "page_footer",
        "y_hint": 808,
    },
    {
        "type": "noise",
        "id": "footer_mod_reference",
        "text": "MOD. (M) 006-720.0313-02 (29) - 16 de abril de 2024",
        "kind": "page_footer",
        "y_hint": 808,
    },
]
