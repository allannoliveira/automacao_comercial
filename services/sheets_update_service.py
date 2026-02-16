def atualizar_status_planilha(sheet, bidding_id, aprovado, link_drive):
    col_ids = sheet.col_values(2)

    for i, val in enumerate(col_ids):
        if val == str(bidding_id):
            linha = i + 1
            sheet.update(f"M{linha}", aprovado)  # aprovado_ia
            sheet.update(f"N{linha}", link_drive)  # link_drive_edital
            break
