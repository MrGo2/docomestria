"""Golden structure spec for 42646161K_CONTRATO.pdf page 2 (CONDICIONES GENERALES).

CaixaBank ASNEF auto-loan (F_AS-5). Reverso: dense two-column legal prose
(clauses 1-14: prestatarios, fiadores, objeto, mora, reembolso, TAE, desistimiento,
reserva de dominio, seguros, cesion...), a contract banner, a 3-column signature row,
and Logalty sidebar / footer noise. No populated form KVs on this page.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/42646161K_CONTRATO.pdf"
PAGE = 2

META = {
    "document_type": "contrato_prestamo_financiacion",
    "annotator": "scaffolder",
    "covers_cases": [
        "condiciones_generales_prose",
        "two_column_legal_clauses",
        "contract_banner_noise",
        "signature_row",
        "logalty_sidebar_noise",
    ],
}


STRUCTURE = [
    # --- Page banner across the top: title + contract identification line ---
    {"type": "noise", "id": "banner_condiciones_generales",
     "text": "CONDICIONES GENERALES", "kind": "watermark", "y_hint": 35.4},
    {"type": "noise", "id": "banner_contrato_ident",
     "text": "Contrato de préstamo de financiación a comprador, impreso nº 4045545 "
             "celebrado entre CAIXABANK PAYMENTS & CONSUMER, E.F.C., E.P., S.A.U. "
             "(también CaixaBank Payments & Consumer) y D/Dª JUAN MARRERO GARCIA",
     "kind": "watermark", "y_hint": 50.4},

    # --- Section: the body of the reverso is general conditions (clauses 1-14) ---
    {"type": "section", "id": "condiciones_generales", "title": "CONDICIONES GENERALES",
     "y_hint": 77.9, "children": [

        {"type": "prose_block", "id": "cg_prestatarios", "label": "1) PRESTATARIOS",
         "text": "1) PRESTATARIOS. Para el caso de intervenir varios prestatarios se "
                 "obligan con carácter solidario al cumplimiento de las obligaciones "
                 "dimanantes del presente contrato.",
         "y_hint": 77.9},

        {"type": "prose_block", "id": "cg_fiadores", "label": "2) FIADORES",
         "text": "2) FIADORES. El/los fiadores afianzan solidariamente entre sí, y con igual "
                 "carácter respecto al deudor/es principal/es, el cumplimiento de todas las "
                 "obligaciones asumidas por el mismo en este contrato con renuncia "
                 "expresa a los beneficios de orden, división y excusión.",
         "y_hint": 110.1},

        {"type": "prose_block", "id": "cg_objeto", "label": "3) OBJETO",
         "text": "3) OBJETO. El presente contrato, de naturaleza mercantil, tiene por objeto "
                 "la concesión de un préstamo de financiación para la adquisición del objeto "
                 "identificado en las condiciones particulares de este contrato.",
         "y_hint": 150.5},

        {"type": "prose_block", "id": "cg_domicilio", "label": "4) DOMICILIO",
         "text": "4) DOMICILIO. Se establece a los efectos prevenidos en la Ley 28/1998, "
                 "que el lugar donde hayan de efectuarse las notificaciones, requerimientos "
                 "y emplazamientos es el domicilio consignado para cada parte en las "
                 "condiciones particulares de este contrato, quedando obligadas las partes "
                 "a comunicarse fehacientemente, cualquier cambio del mismo, sin "
                 "perjuicio de lo establecido en la citada ley, comunicándolo mediante "
                 "escrito dirigido al Registrador de Venta a Plazos. Igualmente se señala "
                 "como domicilio de verificación de pago el de la domiciliación bancaria "
                 "señalada en las condiciones particulares.",
         "y_hint": 182.6},

        {"type": "prose_block", "id": "cg_mora", "label": "5) MORA EN EL PAGO",
         "text": "5) MORA EN EL PAGO. Los deudores que demoren el pago de sus "
                 "deudas vencidas, deberán satisfacer desde el día siguiente a su "
                 "vencimiento un interés moratorio pactado, que se devengará día a día, sin "
                 "necesidad de requerimiento, aplicándose la fórmula del interés simple: I= "
                 "C x R x T : 100. Asimismo, el impago de cualquier cuota establecida en el "
                 "Plan de Amortización, devengará la comisión de devolución acordada por las "
                 "partes en las condiciones particulares de este contrato. Los intereses "
                 "contractuales no satisfechos a sus respectivos vencimientos se "
                 "acumularán mensualmente al capital y como aumento del mismo, "
                 "conforme a lo establecido en el art. 317 del Código de Comercio, "
                 "devengarán nuevos intereses.",
         "y_hint": 264.0},

        {"type": "prose_block", "id": "cg_incumplimiento",
         "label": "6) INCUMPLIMIENTO, VENCIMIENTO ANTICIPADO Y DOCUMENTACIÓN DE LA DEUDA",
         "text": "6) INCUMPLIMIENTO, VENCIMIENTO ANTICIPADO Y DOCUMENTACIÓN "
                 "DE LA DEUDA. La falta de pago de dos cualesquiera de los plazos, o del "
                 "último de ellos, a que se hace referencia en el epígrafe "
                 "RECONOCIMIENTO DE DEUDA facultará al financiador para dar por "
                 "vencido el préstamo, extinguiéndose el aplazamiento y exigiendo, como "
                 "consecuencia el abono de la totalidad de la deuda pendiente, que "
                 "comprenderá la deuda no satisfecha a sus respectivos vencimientos, con "
                 "sus intereses contractuales, la anticipadamente vencida y todo ello, con "
                 "los intereses de demora pactados, comisiones de devolución y demás "
                 "gastos exigibles con arreglo a lo establecido en el presente contrato.",
         "y_hint": 369.4},

        {"type": "prose_block", "id": "cg_reembolso_anticipado", "label": "7) REEMBOLSO ANTICIPADO",
         "text": "7) REEMBOLSO ANTICIPADO. El prestatario podrá reembolsar "
                 "anticipadamente el importe del préstamo de forma total o parcial en "
                 "cualquier momento, comunicándolo por escrito al financiador. "
                 "a) En caso de que el prestatario no tenga la consideración de consumidor "
                 "a los efectos de la Ley de contratos de crédito al consumo el reembolso "
                 "anticipado dará derecho a la retrocesión de los intereses no devengados. "
                 "Los pagos parciales no podrán ser inferiores al 20% del precio del bien "
                 "financiado y el prestatario quedará obligado a abonar la comisión que por "
                 "razón de cancelación anticipada se establece en las condiciones "
                 "particulares de este contrato. Dicha comisión no podrá exceder, en virtud "
                 "de lo establecido en el artículo 9, número 3, de la Ley 28/1998, de 13 de "
                 "julio de Venta a Plazos de Bienes Muebles, del 1,5 por ciento del capital "
                 "reembolsado anticipadamente en los contratos con tipo de interés "
                 "variable y del 3 por ciento en los contratos con tipo de interés fijo. "
                 "b) En caso de que el prestatario tenga la consideración de consumidor a "
                 "los efectos de la Ley de contratos de crédito al consumo, tendrá derecho "
                 "a una reducción del coste total del crédito que comprenda los intereses y "
                 "costes, incluso los ya pagados, correspondientes a la duración del "
                 "contrato que quede por transcurrir. Únicamente en caso de operaciones a "
                 "tipo fijo, deberá abonar una compensación no superior al 1% del importe "
                 "del capital reembolsado anticipadamente si el periodo restante entre el "
                 "reembolso anticipado y la terminación del contrato es superior a un año; "
                 "en caso de que dicho período sea inferior a un año, la compensación no "
                 "será superior al 0,5% del importe del capital reembolsado "
                 "anticipadamente. El importe concreto de la compensación a satisfacer por "
                 "el prestatario será el establecido en las condiciones particulares de este "
                 "contrato. c) El reembolso anticipado de créditos que cuenten con un seguro "
                 "vinculado a la amortización del crédito o a cuya suscripción se haya "
                 "condicionado la concesión del crédito o su concesión en las condiciones "
                 "ofrecidas, dará lugar a la devolución por parte de la entidad aseguradora al "
                 "consumidor de la parte de prima no consumida. "
                 "Ninguna compensación excederá del importe del interés que el "
                 "consumidor habría pagado durante el periodo de tiempo comprendido "
                 "entre el reembolso anticipado y la fecha pactada de finalización del "
                 "contrato de crédito. Conforme a lo previsto en el artículo 4 de la Ley de "
                 "Contratos de Crédito al Consumo, el artículo 30 de dicha Ley no será de "
                 "aplicación en aquellos contratos de préstamo de importe superior a 75.000 euros.",
         "y_hint": 458.8},

        {"type": "prose_block", "id": "cg_tae",
         "label": "8) CÁLCULO Y ELEMENTOS QUE COMPONEN LA T.A.E.",
         "text": "8) CÁLCULO Y ELEMENTOS QUE COMPONEN LA T.A.E. Se entenderá "
                 "por tasa anual equivalente el coste total del crédito, expresado en un "
                 "porcentaje anual sobre la cuantía del crédito concedido. A efectos "
                 "informativos se hace constar que dicha tasa (TAE) se obtiene aplicando la "
                 "fórmula contenida en la Ley 16/2011, de 24 de junio, de contratos de "
                 "crédito al consumo. En caso de interés variable, esta TAE se convierte en "
                 "TAE Variable, la cual se ha calculado bajo la hipótesis de que los índices "
                 "de referencia no varían; por tanto, esta TAE Variable variará con las "
                 "revisiones del tipo de interés.",
         "y_hint": 134.3},

        {"type": "prose_block", "id": "cg_prohibicion_enajenar",
         "label": "9) PROHIBICIÓN DE ENAJENAR",
         "text": "9) PROHIBICIÓN DE ENAJENAR. El prestatario no podrá enajenar o gravar "
                 "el objeto financiado adquirido hasta el completo pago del préstamo sin "
                 "autorización expresa del financiador.",
         "y_hint": 223.6},

        {"type": "prose_block", "id": "cg_reserva_dominio", "label": "10) RESERVA DE DOMINIO",
         "text": "10) RESERVA DE DOMINIO. El dominio del objeto financiado pertenece al "
                 "Financiador hasta el completo pago del mismo.",
         "y_hint": 255.7},

        {"type": "prose_block", "id": "cg_autorizacion_pago", "label": "11) AUTORIZACIÓN DE PAGO",
         "text": "11) AUTORIZACIÓN DE PAGO. El prestatario autoriza al financiador a "
                 "entregar el importe del préstamo al vendedor, siendo el presente contrato "
                 "la carta de autorización más eficaz.",
         "y_hint": 279.7},

        {"type": "prose_block", "id": "cg_seguros", "label": "12) SEGUROS",
         "text": "12) SEGUROS. El comprador deberá suscribir y mantener durante la "
                 "vigencia de este contrato, o de sus prórrogas, un seguro a todo riesgo, "
                 "sobre el bien cuya adquisición se financia, que cubra los daños propios "
                 "del mismo, incluyéndose los supuestos de incendio y robo. Se designa "
                 "como primer beneficiario de la indemnización del seguro al financiador, "
                 "obligándose el comprador a comunicarlo así al asegurador, conviniéndose "
                 "que el asegurador no indemnizará, en cantidad alguna por el siniestro del "
                 "bien, al prestatario, sin el consentimiento previo del financiador, el cual "
                 "queda subrogado en el derecho al cobro de la indemnización que, en su "
                 "caso, le pudiera corresponder al prestatario, hasta la cantidad que quede "
                 "pendiente del préstamo en el momento del siniestro.",
         "y_hint": 311.8},

        {"type": "prose_block", "id": "cg_desistimiento", "label": "13) FACULTAD DE DESISTIMIENTO",
         "text": "13) FACULTAD DE DESISTIMIENTO. "
                 "a) Derecho de desistimiento recogido en la Ley de Venta a Plazos: "
                 "Conforme a lo establecido en el art. 9 de la Ley de Venta a Plazos de "
                 "Bienes Muebles, en el supuesto en que el prestatario tuviera la condición "
                 "de consumidor conforme a la legislación vigente, este podrá ejercitar la "
                 "facultad de desistimiento que le confiere dicha ley y en la forma prevista "
                 "en la misma. En los supuestos de financiación de vehículos a motor se "
                 "estará, en base a lo establecido en el número cuatro de este artículo 9, a "
                 "la posible exclusión o modalización de esta facultad que se haya pactado "
                 "por las partes en las condiciones particulares de este contrato. "
                 "b) Derecho de desistimiento recogido en la Ley de contratos de crédito al "
                 "consumo: En el supuesto de que el prestatario tuviera la condición de "
                 "consumidor, conforme a lo establecido en la Ley de contratos de crédito "
                 "al consumo, este dispondrá de un plazo de catorce días naturales para "
                 "desistir del presente contrato sin indicación de los motivos ni penalización "
                 "alguna u otra compensación, excepto la compensación al prestamista de "
                 "los gastos no reembolsables abonados por este a la administración "
                 "pública. El consumidor que ejerza el derecho de desistimiento deberá: "
                 "- comunicarlo al financiador por cualquier medio admitido en derecho que "
                 "permita dejar constancia de su recepción y contenido. Se considerará que "
                 "se ha respetado el plazo si la notificación se ha enviado antes de la "
                 "expiración del plazo, siempre que haya sido efectuada mediante "
                 "documento en papel o cualquier otro soporte duradero a disposición del "
                 "prestamista y accesible para él. "
                 "- pagar al financiador el capital y el interés acumulado sobre dicho capital, "
                 "calculado al tipo del contrato, desde la fecha de disposición del préstamo "
                 "hasta la fecha efectiva de reembolso del capital al financiador, sin ningún "
                 "retraso indebido, y a más tardar a los treinta días naturales de haber "
                 "enviado la notificación de desistimiento. "
                 "Este derecho de desistimiento no implica en modo alguno el derecho a "
                 "desistir de la compraventa realizada, que se regirá por su normativa "
                 "específica. El derecho de desistimiento recogido en este apartado no regirá en "
                 "aquellos contratos de préstamo de importe superior a 75.000 euros.",
         "y_hint": 409.6},

        {"type": "prose_block", "id": "cg_cesion", "label": "14) CESIÓN",
         "text": "14) CESIÓN. El financiador se reserva el derecho a ceder a tercero los "
                 "derechos y acciones derivados del presente contrato, así como la reserva "
                 "de dominio constituida a su favor y cualquier otra garantía formalizada con "
                 "ocasión del presente contrato, comunicando esta cesión al prestatario.",
         "y_hint": 693.7},
     ]},

    # --- Signature row (three columns), empty boxes ---
    {"type": "signature_placeholder", "id": "firma_prestatarios",
     "label": "Prestatario/s", "value": "", "y_hint": 766.9},
    {"type": "signature_placeholder", "id": "firma_fiadores",
     "label": "Fiador/es", "value": "", "y_hint": 766.9},
    {"type": "signature_placeholder", "id": "firma_financiador",
     "label": "Financiador", "value": "", "y_hint": 766.9},

    # --- Noise: model number, page numbers, Logalty sidebar metadata, footer ---
    {"type": "noise", "id": "modelo_num", "text": "Nº Modelo F_AS-5",
     "kind": "sidebar", "y_hint": 24.5},
    {"type": "noise", "id": "hoja_num", "text": "Hoja nº ......2/11......",
     "kind": "page_number", "y_hint": 33.6},
    {"type": "noise", "id": "pagina_2_22", "text": "2/22",
     "kind": "page_number", "y_hint": 274.3},
    {"type": "noise", "id": "logalty_metadata",
     "text": "Logalty Guid: 001001-0001-000000040208342.par Date: 2020/01/27 T 14:22:49 "
             "CET +0100 Pages: 2/22",
     "kind": "logalty_metadata", "y_hint": 442.3},
    {"type": "noise", "id": "footer_reverso",
     "text": "REVERSO SÓLO APTO PARA LA IMPRESIÓN DE LAS CONDICIONES GENERALES DE ESTE CONTRATO",
     "kind": "watermark", "y_hint": 808.1},
    {"type": "noise", "id": "footer_mod",
     "text": "MOD. (M) 006-720.0313-02 (16) - 17 de julio de 2019",
     "kind": "watermark", "y_hint": 808.1},
]
