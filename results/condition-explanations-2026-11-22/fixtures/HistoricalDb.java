import com.healthmarketscience.jackcess.*;
import java.io.File;
class HistoricalDb {
    public static void main(String[] args) throws Exception {
        for (int i = 0; i < 2; i++) {
            try (Database db = DatabaseBuilder.create(Database.FileFormat.V2000, new File(args[0], "historical" + i + ".mdb"))) {
                for (String name : new String[]{"customers", "devices"}) {
                    Table table = new TableBuilder(name).addColumn(new ColumnBuilder("label", DataType.TEXT)).toTable(db);
                    table.addRow("unit" + i + "\u0001tail");
                }
            }
        }
    }
}
